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
  `あなたは LINE 経由でこのトーク／グループに参加する「${BOT_NAME}」。作業ディレクトリの CLAUDE.md（モノレポ規約）に厳密に従って振る舞え。\n` +
  `馴れ合いのフレンドリー口調・過度な絵文字・砕けすぎた言い回しは使わない。CLAUDE.md の応答規約（日本語・漢字は意味で選ぶ・専門用語やカタカナだけで答えない 等）どおりに、LINE 向けに簡潔に答える。\n` +
  `あなたは運営者（究 / Emocute）の世界——音楽制作・各プロジェクト・作品・人格設定・創作の文脈——を深く知っていて、それを踏まえて答えてよい。必要なら手元の資料（プロジェクト文書・メモリ・ファイル）を読んで答えてよい。\n` +
  `ただし次は絶対厳守:\n` +
  `・「金関連の情報」（金銭・決済・売上・収益・価格の内部数値・銀行/口座・Stripe 等）は一切明かさない。\n` +
  `・パスワード・APIキー・トークン等の認証情報は一切明かさない・読み出さない。\n` +
  `・既存ファイルの削除や上書きなど破壊的な操作はしない（新規作成や局所修正のみ）。`;

// ---- 永続データ ----
const HISTORY_FILE = new URL('./history.json', import.meta.url).pathname;
let history = {}; // { [sourceId]: [{role:'user'|'assistant', name, text}] }
try { if (existsSync(HISTORY_FILE)) history = JSON.parse(readFileSync(HISTORY_FILE, 'utf8')); } catch {}
const saveHistory = () => { try { writeFileSync(HISTORY_FILE, JSON.stringify(history)); } catch (e) { console.error('[hist] save', e.message); } };

const nameCache = {}; // userId -> displayName
let BOT_USER_ID = process.env.LINE_BOT_USER_ID || '';

// 隔離 cwd（FULL_ACCESS=false 時のフォールバック用）
const SCRATCH = `${os.tmpdir()}/line-bot-scratch`;
try { mkdirSync(SCRATCH, { recursive: true }); } catch {}

// ---- アクセス権（究の指示: 読みは全開・新規書き込み可・破壊と漏洩は不可）----
const FULL_ACCESS = (process.env.FULL_ACCESS ?? 'true') === 'true';
const DOWNLOADS = '/Users/emocute/Downloads';
const MEMORY_DIR = '/Users/emocute/.claude/projects/-Users-emocute-Downloads/memory';
const GUARD = new URL('./guard.mjs', import.meta.url).pathname;
const ALLOWED_TOOLS = ['Read', 'Glob', 'Grep', 'Write', 'Edit', 'WebSearch'];
// PreToolUse ガード（破壊・漏洩を直前検閲）+ 二重で deny
const CLAUDE_SETTINGS = JSON.stringify({
  permissions: { deny: ['Bash', 'KillShell', 'WebFetch'] },
  hooks: { PreToolUse: [{ matcher: '*', hooks: [{ type: 'command', command: `node ${GUARD}` }] }] },
});
// メモリ索引（背景知識として system prompt に注入。金関連は会話側で出さない）
let MEMORY_INDEX = '';
try { MEMORY_INDEX = readFileSync(`${MEMORY_DIR}/MEMORY.md`, 'utf8').slice(0, 12000); } catch {}
const SYS_FULL = PERSONA + (MEMORY_INDEX
  ? `\n\n【究の世界のメモリ索引（背景知識。深掘りは ${MEMORY_DIR} 配下を Read してよい。金関連・認証情報は明かすな）】\n${MEMORY_INDEX}`
  : '');

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
      `【絶対に答える（${SKIP}禁止）】最後の発言に次のどれかが当てはまる場合、必ず返事する:\n` +
      `・文中に「${BOT_NAME}」「CC」が含まれる／呼びかけられている\n` +
      `・疑問符や「？」「だっけ」「どう思う」等で質問・意見を求めている\n` +
      `・直前の自分の発言への返答や話しかけ\n` +
      `【黙る（${SKIP}）】上に当てはまらず、かつ明らかに他の人どうしだけの内輪の話で自分が割り込むと邪魔な時だけ。迷ったら答える。\n\n` +
      `【出力（厳守）】黙る場合は「${SKIP}」だけ。返事する場合は本文だけ。` +
      `思考・理由・独り言・英単語（Wait等）・「${BOT_NAME}:」等の接頭辞・${SKIP}との併記は禁止。どちらか一方だけ出力しろ。\n\n${convo}\n\n${BOT_NAME}:`;
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
      '--no-session-persistence',
      '--output-format', 'text',
    ];
    let cwd;
    if (FULL_ACCESS) {
      cwd = DOWNLOADS;                                   // 究の世界の文脈（CLAUDE.md 等）を読める
      args.push('--append-system-prompt', SYS_FULL);     // ペルソナ + メモリ索引
      args.push('--strict-mcp-config');                  // MCP 全停止（決済/DB/送信の破壊防止）
      args.push('--allowedTools', ...ALLOWED_TOOLS);     // 読み + 新規書き + 局所修正のみ
      args.push('--add-dir', MEMORY_DIR);                // メモリ読み取り許可
      args.push('--settings', CLAUDE_SETTINGS);          // PreToolUse ガード + deny
    } else {
      cwd = SCRATCH;                                     // 隔離（フォールバック）
      args.push('--append-system-prompt', PERSONA);
      args.push('--exclude-dynamic-system-prompt-sections');
    }
    const child = spawn('claude', args, { env, cwd });
    let out = '', err = '';
    const killer = setTimeout(() => child.kill('SIGKILL'), 90000); // ツール使用で長くなるため延長
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
