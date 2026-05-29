// line-bot: LINE グループ会話ボット（claude -p で応答、追加課金ゼロ）
// 起動: node --env-file=.env server.mjs
import http from 'node:http';
import crypto from 'node:crypto';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';

// ---- 設定（.env から） ----
const PORT = Number(process.env.PORT || 8787);
const CHANNEL_SECRET = process.env.LINE_CHANNEL_SECRET;
const ACCESS_TOKEN = process.env.LINE_CHANNEL_ACCESS_TOKEN;
const MODEL = process.env.CLAUDE_MODEL || 'sonnet';
const BOT_NAME = process.env.BOT_NAME || 'クロ';
// 'mention_or_prefix'（既定: メンション/接頭辞/DM のみ反応） | 'always'（全発言に反応）
const TRIGGER_MODE = process.env.TRIGGER_MODE || 'mention_or_prefix';
const PREFIXES = (process.env.TRIGGER_PREFIXES || 'クロ,くろ,bot,Bot')
  .split(',').map((s) => s.trim()).filter(Boolean);
const MAX_HISTORY = Number(process.env.MAX_HISTORY || 24);

if (!CHANNEL_SECRET || !ACCESS_TOKEN) {
  console.error('[fatal] LINE_CHANNEL_SECRET と LINE_CHANNEL_ACCESS_TOKEN が必要（.env を作成）');
  process.exit(1);
}

const PERSONA = process.env.BOT_PERSONA ||
  `あなたは LINE グループに参加しているチャット仲間「${BOT_NAME}」。タメ口でフレンドリー、短く返す（基本1〜2文）。` +
  `長文・箇条書き・説明口調は避け、会話のテンポを大事にする。絶対にツールやファイル操作は使わず、テキストだけで即答する。` +
  `運営者やその家族・知人の個人情報（名前・住所・電話・職業など）は一切知らないし、聞かれても答えない。`;

// ---- 永続データ ----
const HISTORY_FILE = new URL('./history.json', import.meta.url).pathname;
let history = {}; // { [sourceId]: [{role:'user'|'assistant', name, text}] }
try { if (existsSync(HISTORY_FILE)) history = JSON.parse(readFileSync(HISTORY_FILE, 'utf8')); } catch {}
const saveHistory = () => { try { writeFileSync(HISTORY_FILE, JSON.stringify(history)); } catch (e) { console.error('[hist] save', e.message); } };

const nameCache = {}; // userId -> displayName
let BOT_USER_ID = process.env.LINE_BOT_USER_ID || '';

// claude を走らせる隔離 cwd（Downloads 配下の CLAUDE.md / メモリを読ませない）
const SCRATCH = `${os.tmpdir()}/line-bot-scratch`;
try { mkdirSync(SCRATCH, { recursive: true }); } catch {}

// ---- LINE API ----
const authHeaders = { Authorization: `Bearer ${ACCESS_TOKEN}` };

async function lineReply(replyToken, text) {
  const r = await fetch('https://api.line.me/v2/bot/message/reply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body: JSON.stringify({ replyToken, messages: [{ type: 'text', text: text.slice(0, 4900) }] }),
  });
  if (!r.ok) console.error('[reply]', r.status, (await r.text()).slice(0, 200));
  return r.ok;
}

async function linePush(to, text) {
  const r = await fetch('https://api.line.me/v2/bot/message/push', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body: JSON.stringify({ to, messages: [{ type: 'text', text: text.slice(0, 4900) }] }),
  });
  if (!r.ok) console.error('[push]', r.status, (await r.text()).slice(0, 200));
}

async function resolveName(source, userId) {
  if (!userId) return '誰か';
  if (nameCache[userId]) return nameCache[userId];
  let url;
  if (source.type === 'group') url = `https://api.line.me/v2/bot/group/${source.groupId}/member/${userId}`;
  else if (source.type === 'room') url = `https://api.line.me/v2/bot/room/${source.roomId}/member/${userId}`;
  else url = `https://api.line.me/v2/bot/profile/${userId}`;
  try {
    const r = await fetch(url, { headers: authHeaders });
    if (r.ok) { const j = await r.json(); nameCache[userId] = j.displayName || '誰か'; return nameCache[userId]; }
  } catch {}
  return '誰か';
}

async function fetchBotInfo() {
  try {
    const r = await fetch('https://api.line.me/v2/bot/info', { headers: authHeaders });
    if (r.ok) { const j = await r.json(); if (!BOT_USER_ID) BOT_USER_ID = j.userId || ''; console.log(`[bot] ${j.displayName} (${j.userId})`); }
  } catch (e) { console.error('[bot] info', e.message); }
}

// ---- ロジック ----
const sourceId = (s) => s.groupId || s.roomId || s.userId;

function shouldRespond(ev) {
  if (ev.source.type === 'user') return true; // DM は常に反応
  // always / natural は全メッセージを受け取り claude 側で判断
  if (TRIGGER_MODE === 'always' || TRIGGER_MODE === 'natural') return true;
  const text = ev.message.text || '';
  if (BOT_USER_ID && ev.message.mention?.mentionees?.some((m) => m.userId === BOT_USER_ID)) return true;
  const lower = text.toLowerCase();
  return PREFIXES.some((p) => lower.includes(p.toLowerCase()));
}

const SKIP = '[SKIP]';

function buildPrompt(sid, natural) {
  const convo = (history[sid] || [])
    .map((m) => (m.role === 'assistant' ? `${BOT_NAME}: ${m.text}` : `${m.name}: ${m.text}`))
    .join('\n');
  if (natural) {
    return `以下は LINE グループの会話ログ。あなたは「${BOT_NAME}」としてこのグループの一員。\n` +
      `基本は会話に参加する。次のどれかなら必ず短く返事しろ:\n` +
      `・「${BOT_NAME}」と呼ばれている／名前が出ている\n` +
      `・質問されている、意見を求められている\n` +
      `・最後の発言が自分への返答や話しかけ\n` +
      `・乗れる話題で一言あると会話が弾む\n` +
      `逆に、明らかに他の人だけで込み入った話をしていて割り込むと邪魔な時だけ黙る。迷ったら返事する側に倒す。\n\n` +
      `【出力ルール（厳守）】黙る場合は「${SKIP}」の5文字だけを出力。返事する場合は返事の本文だけを出力。` +
      `思考・理由・独り言・英単語（Wait等）・「${BOT_NAME}:」のような接頭辞・${SKIP}との併記は一切禁止。どちらか一方だけ。\n\n${convo}\n\n${BOT_NAME}:`;
  }
  return `以下は LINE グループの会話ログ。最後の発言に対して ${BOT_NAME} として自然に短く返事しろ。` +
    `返事の本文だけ出力すること（「${BOT_NAME}:」などの接頭辞は付けない）。\n\n${convo}\n\n${BOT_NAME}:`;
}

function runClaude(prompt) {
  return new Promise((resolve) => {
    const env = { ...process.env };
    delete env.CLAUDECODE;
    delete env.CLAUDE_CODE_ENTRYPOINT;
    const args = [
      '-p', prompt,
      '--model', MODEL,
      '--append-system-prompt', PERSONA,
      '--no-session-persistence',
      '--exclude-dynamic-system-prompt-sections',
      '--output-format', 'text',
    ];
    const child = spawn('claude', args, { env, cwd: SCRATCH });
    let out = '', err = '';
    const killer = setTimeout(() => child.kill('SIGKILL'), 55000);
    child.stdout.on('data', (d) => (out += d));
    child.stderr.on('data', (d) => (err += d));
    child.on('close', (code) => {
      clearTimeout(killer);
      if (code === 0 && out.trim()) resolve(out.trim());
      else { console.error('[claude] exit', code, err.slice(0, 300)); resolve(null); }
    });
    child.on('error', (e) => { clearTimeout(killer); console.error('[claude] spawn', e.message); resolve(null); });
  });
}

function pushHistory(sid, entry) {
  history[sid] = history[sid] || [];
  history[sid].push(entry);
  if (history[sid].length > MAX_HISTORY) history[sid] = history[sid].slice(-MAX_HISTORY);
}

async function handleEvent(ev) {
  console.log(`[event] type=${ev.type} msgType=${ev.message?.type} srcType=${ev.source?.type}`);
  if (ev.type !== 'message' || ev.message?.type !== 'text') return;
  const sid = sourceId(ev.source);
  const name = await resolveName(ev.source, ev.source.userId);
  pushHistory(sid, { role: 'user', name, text: ev.message.text });
  saveHistory();

  const respond = shouldRespond(ev);
  console.log(`[event] "${ev.message.text}" from ${name} → respond=${respond}`);
  if (!respond) return;
  const natural = TRIGGER_MODE === 'natural' && ev.source.type !== 'user';
  const answer = await runClaude(buildPrompt(sid, natural));
  console.log(`[claude] → ${answer ? JSON.stringify(answer.slice(0, 80)) : 'NULL'}`);
  if (!answer) return;
  let text = answer.trim();
  if (natural) {
    if (text.replace(/[「」\[\]\s]/g, '').toUpperCase() === 'SKIP') { console.log('[natural] SKIP（黙る）'); return; }
    text = text.replace(/\[?SKIP\]?/gi, '').trim(); // 万一の混在を除去
    if (!text) { console.log('[natural] 除去後 空 → 黙る'); return; }
  }
  pushHistory(sid, { role: 'assistant', text });
  saveHistory();

  const ok = await lineReply(ev.replyToken, text); // 無料
  console.log(`[reply] ${ok ? 'ok' : 'failed → push fallback'}`);
  if (!ok) await linePush(sid, text); // token 失効時のみ（push は月200通枠）
}

// ---- HTTP サーバ ----
const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/webhook') {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      const raw = Buffer.concat(chunks);
      const expected = crypto.createHmac('sha256', CHANNEL_SECRET).update(raw).digest('base64');
      if (req.headers['x-line-signature'] !== expected) {
        console.log('[webhook] BAD SIGNATURE (secret mismatch?)');
        res.writeHead(401); res.end('bad signature'); return;
      }
      res.writeHead(200); res.end('OK'); // LINE には即 200（処理は非同期）
      let body; try { body = JSON.parse(raw.toString('utf8')); } catch { return; }
      console.log(`[webhook] received ${(body.events || []).length} event(s)`);
      for (const ev of body.events || []) handleEvent(ev).catch((e) => console.error('[handle]', e.message));
    });
    return;
  }
  if (req.url === '/health') { res.writeHead(200); res.end('ok'); return; }
  res.writeHead(404); res.end();
});

server.listen(PORT, async () => {
  await fetchBotInfo();
  console.log(`[line-bot] :${PORT}  model=${MODEL}  trigger=${TRIGGER_MODE}  prefixes=[${PREFIXES.join(',')}]`);
});
