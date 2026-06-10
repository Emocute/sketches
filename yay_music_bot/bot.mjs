// yay_music_bot — 純音楽BOT（Yay 通話 / YouTube → Agora RTC publish）。
// yay_bot（究の個人用フル機能bot）から分離した独立PJ。会話/人格/聴取/録音/開発ツールは持たない。
// 唯一の声機能＝入退室の読み上げ（名前を短く言うだけ・LLM不使用＝コンテキスト消費ゼロ）。
//
// 流れ:
//   1) yay_api.py で通話creds(agora_channel/agora_token/rtm_token/uid)を取得（待ち受け→自動join）
//   2) 制御下Chromiumで agora_client.html を開き Agoraチャンネルへ join
//   3) RTM受信をpollingし、音楽コマンド(/play 等)と自然言語(「○○かけて」)を実行
//   4) /play は yt-dlp で解決→RTC publish。キューと自動送り対応。
//
// 起動: node bot.mjs            （現在参加中の通話を自動発見）
//      YAY_CALL_ID=<id> node bot.mjs （call_id 明示）
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { CONFIG } from './config.mjs';
import * as agora from './lib/agora.mjs';
import * as music from './lib/music_agora.mjs';
import * as tts from './lib/tts.mjs';   // 入退室の読み上げのみ（会話には使わない＝LLM不使用）

const PY = fileURLToPath(new URL('./.venv/bin/python', import.meta.url));
const API = fileURLToPath(new URL('./yay_api.py', import.meta.url));
const SELF_UID = String(process.env.YAY_SELF_UID || '11320230');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const loadState = () => (existsSync(CONFIG.stateFile) ? JSON.parse(readFileSync(CONFIG.stateFile, 'utf8')) : { seen: [] });
const saveState = (s) => { try { writeFileSync(CONFIG.stateFile, JSON.stringify(s, null, 2)); } catch (e) { console.error('state', e.message); } };

// yay_api.py を叩いて creds JSON を得る（最終行が JSON）。
//   発見uid = YAY_WATCH_UID(別アカ運用時) があればそれ、無ければ SELF_UID。
const DISCOVER_UID = String(process.env.YAY_WATCH_UID || SELF_UID);
function fetchCreds() {
  const args = process.env.YAY_CALL_ID ? ['creds', String(process.env.YAY_CALL_ID)] : ['active', DISCOVER_UID];
  return new Promise((resolve, reject) => {
    execFile(PY, [API, ...args], { timeout: 30000 }, (err, stdout, stderr) => {
      const lines = (stdout || '').trim().split('\n').filter(Boolean);
      let json = null;
      for (let i = lines.length - 1; i >= 0; i--) { try { json = JSON.parse(lines[i]); break; } catch {} }
      if (!json) return reject(new Error('creds JSON 解析不可: ' + (stderr || stdout || err?.message)));
      resolve(json);
    });
  });
}

// RTM の生メッセージ → {id, author, text, type}。Yay通話チャットは "chat {JSON}" 形式。
function parseMsg(m) {
  let raw = m.message, author = String(m.publisher ?? '?');
  if (typeof raw !== 'string') { try { raw = JSON.stringify(raw); } catch { raw = String(raw); } }
  let type = 'chat', body = raw;
  const mt = /^(\w+)\s+([\[{][\s\S]*)$/.exec(raw);
  if (mt) { type = mt[1].toLowerCase(); body = mt[2]; }
  let text = body, msgId = null;
  try {
    const j = JSON.parse(body);
    if (j && typeof j === 'object') { text = j.text ?? j.message ?? j.content ?? j.body ?? ''; msgId = j.id ?? null; }
  } catch {}
  if (type !== 'chat') text = '';
  text = String(text || '').trim();
  return { id: msgId ? `id:${msgId}` : `${author}|${m.ts}|${text}`, author, text, type };
}

// Yayが表示できる送信エンベロープ。受信と同形式。
function yayEnvelope(text) {
  const now = Date.now();
  const payload = { text: String(text), created_at_seconds: Math.floor(now / 1000), id: `${SELF_UID}_${now}` };
  return 'chat ' + JSON.stringify(payload);
}
const sendYayChat = (p, text) => agora.sendChat(p, yayEnvelope(text));

let page, fileBase, creds;

// ===== 音楽状態 =====
let queue = [];        // 未再生キュー（query文字列）
let nowQuery = null;   // 再生中の曲名/ラベル
let starting = false;  // 多重起動ガード
let lastVol = Number(process.env.YAY_MUSIC_VOL || 15);
let lastTtsVol = Number(process.env.YAY_TTS_VOL || (CONFIG.jingle?.ttsVol ?? 15)); // 読み上げ音量 0-100（/ttsvol で変更）
let queueRepeat = false; // キュー全体リピート（/qr）。ON で流し終えた曲を末尾へ戻して循環。

const PLAYLIST_LIMIT = 100;   // YouTube プレイリスト展開の上限曲数（チャット氾濫・過負荷防止）
// 1入力 → 複数曲（カンマ/読点/改行区切り）。空要素は捨てる。
function splitSongs(s) {
  return String(s).split(/\s*[,、，\n]+\s*/).map((x) => x.trim()).filter(Boolean);
}
// 1メッセージ → 複数コマンド行に分割。先頭が ! or / の行＝新コマンド。
// コマンドでない行は直前のコマンドへ ", " で追記（曲名を縦に並べて複数投入できる）。
function splitCommandLines(text) {
  const lines = String(text).split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const cmds = [];
  for (const l of lines) {
    if (/^[!\/]/.test(l)) cmds.push(l);
    else if (cmds.length) cmds[cmds.length - 1] += ', ' + l;
  }
  return cmds;
}
// YouTube プレイリストURL 判定（list= を持つ youtube/youtu.be リンク）。
function isPlaylistUrl(u) {
  return /^https?:\/\//i.test(u) && /(youtube\.com|youtu\.be)/i.test(u) && /[?&]list=/i.test(u);
}
// キュー表示用ラベル（長いURLは動画IDに短縮、曲名はそのまま）。
function qLabel(s) {
  if (!/^https?:\/\//i.test(s)) return s;
  const m = s.match(/[?&]v=([\w-]{6,})/) || s.match(/youtu\.be\/([\w-]{6,})/);
  return m ? `▶ ${m[1]}` : s.slice(0, 48);
}

// ===== 入退室の読み上げ（jingle）=====
// 名簿(yay_api.py members)を周期取得し、前回との差分で join/leave を検出して名前で短く挨拶。
// 声は既存 playTTS（音楽は止めず ttsGain に乗せ、TTS中は音楽を自動ダッキング）。LLMは一切使わない。
const JC = () => CONFIG.jingle || {};
let jingleOn = JC().enabled !== false;
const roster = new Map();      // Yay userId(str) → { nick, lastSeen, present }
let memberSeeded = false;      // 初回は無言シード（既存メンバーに連打しない）
let lastMemberPollAt = 0;
let lastJingleAt = 0;
let jingleQueue = [];          // {kind:'join'|'leave', nick, returning}

// 名簿取得（python 1回 spawn、最終行 JSON）。
function fetchMembers(callId) {
  return new Promise((resolve) => {
    execFile(PY, [API, 'members', String(callId)], { timeout: 20000 }, (err, stdout) => {
      const lines = (stdout || '').trim().split('\n').filter(Boolean);
      for (let i = lines.length - 1; i >= 0; i--) { try { return resolve(JSON.parse(lines[i])); } catch {} }
      resolve({ ok: false });
    });
  });
}
function greetWord() {
  const h = new Date().getHours();
  if (h >= 5 && h < 11) return 'おはよ';
  if (h >= 11 && h < 18) return 'やっほー';
  return 'こんばんは';
}
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
function jingleLine({ kind, nick, returning }) {
  const who = nick || '誰か';
  if (kind === 'leave') return pick([`${who} またね`, `${who} ばいばい`, `${who} おつかれ`, `${who}、また来てね`]);
  if (returning) return pick([`${who} おかえり`, `${who} 戻ってきた`, `おっ ${who} おかえり`]);
  const g = greetWord();
  return pick([`${who} ${g}！いらっしゃい`, `${g} ${who}！来てくれた`, `${who} いらっしゃい`, `お、${who} 来た！${g}`]);
}
function inQuietHours() {
  const qh = JC().quietHours;
  if (!Array.isArray(qh) || qh.length !== 2) return false;
  const h = new Date().getHours(); const [a, b] = qh;
  return a <= b ? (h >= a && h < b) : (h >= a || h < b);   // 跨ぎ(例: 23-7)も対応
}
// あいさつを声で（音楽を止めず ttsGain に乗せ自動ダッキング）。quietHours/voice=false なら無声。
async function sayJingle(text) {
  if (JC().voice === false || inQuietHours()) return;
  try {
    const r = await tts.speak(text, { voice: JC().voiceKey || null });
    if (!r.ok || !r.file) return;
    await agora.playTTS(page, agora.fileUrl(fileBase, r.file)).catch((e) => console.error('[greet] playTTS', e.message));
  } catch (e) { console.error('[greet] say', e.message); }
}
// 名簿ポーリング＋差分（throttle はここで持つ。loop から毎周回呼んでよい）。
async function pollMembersAndDiff() {
  if (!jingleOn) return;
  const callId = process.env.YAY_CALL_ID || creds?.conference_id;
  if (!callId) return;
  const now = Date.now();
  if (now - lastMemberPollAt < (JC().pollMs || 12000)) return;
  lastMemberPollAt = now;
  let res; try { res = await fetchMembers(callId); } catch { return; }
  if (!res?.ok || !Array.isArray(res.users)) return;
  const selfId = String(SELF_UID);
  const seenNow = new Set();
  for (const u of res.users) {
    const id = String(u.id ?? '');
    if (!id || id === selfId) continue;     // 自分(Emo Music)は除外
    seenNow.add(id);
    const prev = roster.get(id);
    const nick = u.nickname || prev?.nick || null;
    if (!prev || !prev.present) {
      if (memberSeeded) {
        const gap = prev ? (now - (prev.lastSeen || 0)) : Infinity;
        const flap = prev && gap < 5000;                          // 5秒以内の瞬断=回線フラップ→無音
        const returning = !!prev && gap < (JC().rejoinGraceMs || 90000);
        if (!flap) jingleQueue.push({ kind: 'join', nick, returning });
      }
    }
    roster.set(id, { nick, lastSeen: now, present: true });
  }
  for (const [id, info] of roster) {
    if (info.present && !seenNow.has(id)) {
      info.present = false; info.lastSeen = now;
      if (memberSeeded) jingleQueue.push({ kind: 'leave', nick: info.nick, returning: false });
    }
  }
  const cap = JC().maxQueue || 8;
  if (jingleQueue.length > cap) jingleQueue = jingleQueue.slice(-cap);
  memberSeeded = true;
}
// キュー消化（rate limit。1周回1件）。
async function drainJingle() {
  if (!jingleOn || !jingleQueue.length) return;
  const now = Date.now();
  if (now - lastJingleAt < (JC().minGapMs || 8000)) return;
  const j = jingleQueue.shift();
  lastJingleAt = now;
  const line = jingleLine(j);
  const emoji = j.kind === 'leave' ? '👋' : '🎉';
  try { await sendYayChat(page, `${emoji} ${line}`); } catch (e) { console.error('[greet] chat', e.message); }
  await sayJingle(line);
  console.log(`  ${emoji} greet:`, line);
}
function presentCount() { return [...roster.values()].filter((r) => r.present).length; }

// canonical → [aliases]（`/` でも `!` でも発火）。音楽コマンドのみ。
const CMD = {
  help:   ['help', 'h', '?'],
  play:   ['play', 'p', 'pl'],
  queue:  ['queue', 'q', 'add'],
  skip:   ['skip', 's', 'next', 'n'],
  stop:   ['stop', 'x'],
  pause:  ['pause', 'ps'],
  resume: ['resume', 're', 'r'],
  vol:    ['vol', 'volume', 'v'],
  volup:  ['volup', 'vu', '音量上げ'],
  voldown:['voldown', 'vd', '音量下げ'],
  np:     ['np', 'now', 'nowplaying'],
  loop:   ['loop', 'l'],
  live:   ['live', 'lv'],
  dev:    ['devices', 'dev', 'd'],
  clear:  ['clear', 'cls', 'c'],
  qlist:  ['ql', 'qlist', 'きゅー', 'リスト'],
  qdel:   ['qd', 'qdel', 'rm', '消'],
  qup:    ['qu', 'qup', 'up', '上'],
  qdn:    ['qj', 'qdn', 'down', '下'],
  qrepeat:['qr', 'repeat', 'rp', 'リピート', '繰り返し'],   // キュー全体リピート on/off（/l は一曲ループ）
  qshuffle:['qsh', 'shuffle', 'shuf', 'シャッフル', 'ランダム'],  // キューをランダム並べ替え
  ttsvol: ['ttsvol', 'vv', '声量', '読み上げ音量'],   // 読み上げ(あいさつ)の音量 0-100
  ping:   ['ping', 'pi'],
  greet:  ['greet', 'あいさつ', '入退室'],   // 入退室の読み上げ ON/OFF
  leave:  ['leave', 'bye'],
};
const ALIAS = {}; for (const [k, vs] of Object.entries(CMD)) for (const v of vs) ALIAS[v] = k;

// 2層ヘルプ: 引数なし=みんなが使う基本 / all=究が使う専門。各項目を絵文字で統一（表記揺れ防止）。
function renderHelp(arg) {
  const pro = /^(all|full|pro|全部|詳細|専門|a)$/i.test(String(arg || '').trim());
  if (!pro) {
    return [
      '🎧 音楽BOT（専門コマンドは /h all）',
      '▶️ /p 曲名 再生（「○○かけて」でも可）',
      '⏭️ /s スキップ  ⏹️ /x 停止',
      '⏸️ /ps 一時停止  ⏯️ /r 再開',
      '🔊 /v 0-100 音量  🎵 /np 再生中  📜 /ql キュー一覧',
    ].join('\n');
  }
  return [
    '🎧 専門コマンド',
    '🔂 /l 一曲ループ  🔁 /qr キュー全体  🔀 /qsh シャッフル',
    '🔼 /qu N 前へ  🔽 /qj N 後ろへ  🗑️ /qd N 削除  🧹 /c 全消去',
    '🗣️ /ttsvol 0-100 読み上げ音量  👋 /greet 入退室読み上げ',
    '📡 /lv 音声配信  🎛️ /d 入力一覧  🔉 /vu /vd 音量±10',
    '➕ 複数曲「曲A,曲B」  📋 YT再生リストURLは全曲展開  🚪 /bye 退出',
  ].join('\n');
}
const onoff = (b) => (b ? '🟢ON' : '⚪OFF');
function statusLine() {
  const rep = queueRepeat ? ' 🔁' : '';
  return nowQuery ? `🎵 再生中: ${nowQuery}${rep}${queue.length ? ` / 次(${queue.length})` : ''}` : (queue.length ? `📜 キュー${queue.length}件${rep}` : '🎵 再生なし');
}

// 1曲を解決→publish（real-time）。解決した正式タイトルを「流す前」にチャットへ出す。
async function startTrack(query) {
  starting = true;
  try {
    let r;
    try { r = await music.resolveStreamUrl(query); }
    catch (e) { console.error('  resolve失敗:', e.message); return { ok: false, notfound: true, query }; }
    const title = r.title || query;
    await sendYayChat(page, `🎵 ${title}`).catch(() => {});
    await agora.playUrl(page, agora.streamUrl(fileBase, r.url));
    nowQuery = title;
    return { ok: true, title };
  } finally { starting = false; }
}
const notFoundMsg = (q) => `❌ 見つかりませんでした: ${q}`;

// 自然言語 → スラッシュコマンド（通話の全員に適用）。制御意図でなければ null。
function nlToCommand(text) {
  const t = String(text).trim();
  let m;
  if (/(一時停止|ポーズ|ちょっと止め)/.test(t)) return '/pause';
  if (/(再開|続きから|戻して再生)/.test(t)) return '/resume';
  if (/(止めて|停めて|ストップ|止めろ|停止|音楽.*消)/.test(t)) return '/stop';
  if (/(次の?曲|次に?して|次いって|スキップ|とばして|飛ばして|チェンジして)/.test(t)) return '/skip';
  if ((m = t.match(/(?:音量|ボリューム|ボリュ)\D*?(\d{1,3}(?:\.\d+)?)/))) return `/vol ${m[1]}`;
  if (/(?:音量|ボリューム|音)/.test(t) && /(上げ|大きく|でかく|あげて|うるさ)/.test(t)) return '/volup';
  if (/(?:音量|ボリューム|音)/.test(t) && /(下げ|小さく|さげて|ちいさ|静か|絞)/.test(t)) return '/voldown';
  const pv = t.match(/(かけて|流して|再生して|プレイして|聴きたい|聞きたい|かけろ|流せ|プレイ|かけ)/);
  if (pv) {
    let q = t.slice(0, pv.index).trim();
    q = q.replace(/^(で|の|を)\s*/, '').replace(/(を|の曲|って)\s*$/, '').trim();
    if (!q) return null;
    return `/play ${q}`;
  }
  return null;
}

function renderQueue() {
  const rep = queueRepeat ? ' 🔁' : '';
  if (!queue.length) return nowQuery ? `🎵 再生中: ${nowQuery}${rep}\n📜 キューは空` : '📜 キューは空（/p 曲名 で再生）';
  const head = nowQuery ? `🎵 再生中: ${nowQuery}${rep}\n` : '';
  const MAX = 15;   // 長大キュー（プレイリスト展開等）はチャット氾濫を防ぐため先頭 N 件のみ表示
  const lines = queue.slice(0, MAX).map((s, i) => `${i + 1}. ${qLabel(s)}`).join('\n');
  const more = queue.length > MAX ? `\n…他${queue.length - MAX}曲` : '';
  return head + `📜 キュー(${queue.length}):\n` + lines + more;
}
function qIndex(q) { const n = parseInt(q, 10); return (Number.isInteger(n) && n >= 1 && n <= queue.length) ? n - 1 : -1; }

async function handleCommand(text) {
  const mm = String(text).match(/^\s*[!\/]\s*(\S+)\s*([\s\S]*)$/);
  if (!mm) return null;
  const cmd = ALIAS[mm[1].toLowerCase()];
  const q = (mm[2] || '').trim();
  if (!cmd) return null;
  try {
    switch (cmd) {
      case 'help': return renderHelp(q);
      case 'ping': return '🏓 pong';
      case 'play':
      case 'queue': {
        if (!q) return renderQueue();           // 引数なし = 番号付き一覧
        let songs = splitSongs(q);              // カンマ/読点/改行区切りで複数曲対応
        // YouTube プレイリストURL は各動画へ展開（展開失敗時はそのURLを単曲扱い）
        let plNote = '';
        if (songs.some(isPlaylistUrl)) {
          const ex = [];
          for (const s of songs) {
            if (!isPlaylistUrl(s)) { ex.push(s); continue; }
            try {
              const items = await music.expandPlaylist(s, { limit: PLAYLIST_LIMIT });
              if (items.length) { ex.push(...items.map((it) => it.url)); plNote += `📃 プレイリスト展開: ${items.length}曲\n`; }
              else { ex.push(s); plNote += '⚠ プレイリストが空（単曲扱い）\n'; }
            } catch (e) { console.error('playlist expand', e.message); ex.push(s); plNote += '⚠ プレイリスト展開失敗（単曲扱い）\n'; }
          }
          songs = ex;
        }
        if (!songs.length) return notFoundMsg(q);
        // 複数曲: 空いてれば先頭を即再生、残りをキュー。再生中なら全部キュー末尾へ。
        if (songs.length > 1) {
          let started = null; const added = [];
          for (const s of songs) {
            if (!nowQuery && !starting && !started) {
              const r = await startTrack(s);
              if (r.ok) started = s; else { queue.push(s); added.push(s); }
            } else { queue.push(s); added.push(s); }
          }
          const head = started ? `▶ 再生: ${qLabel(started)}\n` : '';
          return `${plNote}${head}➕ ${added.length}曲をキューに追加\n` + renderQueue();
        }
        // 単曲
        const one = songs[0];
        if (!nowQuery && !starting) { const r = await startTrack(one); return r.ok ? (plNote || null) : notFoundMsg(one); }
        queue.push(one);
        return `${plNote}➕ キューに追加(${queue.length}): ${qLabel(one)}`;
      }
      case 'qlist': return renderQueue();
      case 'qdel': {
        if (!queue.length) return '📜 キューは空';
        const i = qIndex(q); if (i < 0) return `番号を指定して（1〜${queue.length}）例: /qd 2`;
        const [x] = queue.splice(i, 1);
        return `🗑 ${i + 1}. ${x} を削除\n` + renderQueue();
      }
      case 'qup': {
        const i = qIndex(q); if (i < 0) return `番号を指定して（1〜${queue.length}）例: /qu 2`;
        if (i === 0) return 'もう先頭\n' + renderQueue();
        [queue[i - 1], queue[i]] = [queue[i], queue[i - 1]];
        return `⬆ ${i + 1}→${i}\n` + renderQueue();
      }
      case 'qdn': {
        const i = qIndex(q); if (i < 0) return `番号を指定して（1〜${queue.length}）例: /qj 2`;
        if (i === queue.length - 1) return 'もう末尾\n' + renderQueue();
        [queue[i + 1], queue[i]] = [queue[i], queue[i + 1]];
        return `⬇ ${i + 1}→${i + 2}\n` + renderQueue();
      }
      case 'qrepeat': {
        if (/^(on|オン|1)$/i.test(q)) queueRepeat = true;
        else if (/^(off|オフ|0)$/i.test(q)) queueRepeat = false;
        else queueRepeat = !queueRepeat;
        return queueRepeat ? '🔁 キューリピートON（最後まで流したら頭から繰り返す）' : '➡ キューリピートOFF';
      }
      case 'qshuffle': {
        if (queue.length < 2) return 'シャッフルする曲が足りない（2曲以上必要）\n' + renderQueue();
        for (let i = queue.length - 1; i > 0; i--) {   // Fisher-Yates
          const j = Math.floor(Math.random() * (i + 1));
          [queue[i], queue[j]] = [queue[j], queue[i]];
        }
        return `🔀 キューをシャッフル(${queue.length}曲)\n` + renderQueue();
      }
      case 'skip':
        await agora.stopMusic(page); nowQuery = null;
        return queue.length ? '⏭ スキップ' : '⏭ スキップ（キュー空）';
      case 'stop':
        queue = []; await agora.stopMusic(page); nowQuery = null;
        return '⏹ 停止（キューも消去）';
      case 'clear': queue = []; return '🧹 キュー消去';
      case 'pause': await agora.pauseMusic(page); return '⏸ 一時停止';
      case 'resume': await agora.resumeMusic(page); return '▶ 再開';
      case 'vol': { const r = await agora.setMusicVolume(page, q); if (r?.ok) lastVol = r.vol; return r?.ok ? `🔊 音量 ${r.vol}` : '音量は 0〜100・小数可（例: /v 15, /v 0.5）'; }
      case 'volup': { const v = Math.min(100, Math.round((lastVol + (lastVol < 2 ? 0.5 : 10)) * 100) / 100); const r = await agora.setMusicVolume(page, v); if (r?.ok) lastVol = r.vol; return `🔊 音量 ${r?.vol ?? v}`; }
      case 'voldown': { const v = Math.max(0, Math.round((lastVol - (lastVol <= 2 ? 0.5 : 10)) * 100) / 100); const r = await agora.setMusicVolume(page, v); if (r?.ok) lastVol = r.vol; return `🔉 音量 ${r?.vol ?? v}`; }
      case 'np': return statusLine();
      case 'loop': { const r = await agora.setLoop(page); return r?.loop ? '🔁 一曲ループON' : '➡ 一曲ループOFF'; }
      case 'live': await agora.playLive(page, q || null); nowQuery = 'live'; return `▶ システム音声配信中${q ? '（' + q + '）' : ''}`;
      case 'dev': { const ds = await agora.listAudioInputs(page); return '🎤 入力: ' + (ds.map((d) => d.label).filter(Boolean).join(' / ') || 'なし'); }
      case 'ttsvol': {  // 読み上げ音量 0-100
        if (!q) return `🔈 読み上げ音量: ${lastTtsVol}（変更は /ttsvol 0-100）`;
        const r = await agora.setTtsVolume(page, q);
        if (r?.ok) lastTtsVol = r.vol;
        return r?.ok ? `🔈 読み上げ音量 ${r.vol}` : '音量は 0〜100・小数可（例: /ttsvol 15, /ttsvol 0.5）';
      }
      case 'greet': {
        const a = q.toLowerCase();
        if (a === '' || a === '?' || a === 'status') return `🎉 入退室あいさつ: ${jingleOn ? 'ON' : 'OFF'}（声${JC().voice === false ? 'OFF' : 'ON'} / 在室${presentCount()}人）`;
        if (['off', 'stop', 'オフ', '0', 'なし'].includes(a)) { jingleOn = false; jingleQueue = []; return '🤫 入退室あいさつOFF'; }
        if (['on', 'オン', '1'].includes(a)) { jingleOn = true; return '🎉 入退室あいさつON'; }
        jingleOn = !jingleOn; if (!jingleOn) jingleQueue = [];
        return jingleOn ? '🎉 入退室あいさつON' : '🤫 入退室あいさつOFF';
      }
      case 'leave': await agora.leave(page); nowQuery = null; queue = []; return '👋 通話から抜けた';
      default: return null;
    }
  } catch (e) { return `エラー: ${e.message}`; }
}

// 1メッセージ内の複数コマンド行を順に実行し、応答を「―」区切りでまとめて返す（コマンドでなければ null）。
async function runCommands(text) {
  const cmds = splitCommandLines(text);
  if (!cmds.length) return null;
  const outs = [];
  for (const c of cmds) {
    const r = await handleCommand(c);
    if (r) outs.push(r);
  }
  return outs.length ? outs.join('\n―\n') : '';
}

async function main() {
  const WAIT_MS = Number(process.env.YAY_WAIT_MS || 15000);
  console.log('[music] 通話待ち受け開始（通話に入ったら自動参加）…');
  for (;;) {
    creds = await fetchCreds().catch((e) => ({ ok: false, error: e.message }));
    if (creds && creds.ok) break;
    const reason = creds?.error || '不明';
    if (!/参加中の通話が無い/.test(String(reason))) console.log('[music] creds 取得待ち:', reason);
    await sleep(WAIT_MS);
  }
  console.log('[music] ✓ 通話発見→自動参加 channel=%s uid=%s', creds.channel, creds.uid);

  const fs = await agora.startFileServer(0);
  fileBase = `http://127.0.0.1:${fs.port}`;
  console.log('[music] file server', fileBase);

  const a = await agora.launchAgora({ headless: !process.env.HEADFUL });
  page = a.page;
  const joined = await agora.join(page, {
    appId: creds.app_id, channel: creds.channel,
    rtcToken: creds.rtc_token, uid: creds.conference_call_user_uuid,
    rtmToken: creds.rtm_token, rtmUid: creds.conference_call_user_uuid,
  });
  console.log('[music] join:', JSON.stringify(joined));
  if (!joined.rtc?.ok) console.error('[music] ⚠ RTC参加失敗（音楽流せない）:', joined.rtc?.error);
  if (!joined.rtm?.ok) console.error('[music] ⚠ RTM参加失敗（コマンド読/送不可）:', joined.rtm?.error);

  const SELF_RTM = String(creds.conference_call_user_uuid || SELF_UID);
  console.log('[music] self RTM id =', SELF_RTM);

  if (process.env.YAY_MUSIC_VOL) { const r = await agora.setMusicVolume(page, process.env.YAY_MUSIC_VOL); console.log('[music] 初期音量', r?.vol); }
  try { const r = await agora.setTtsVolume(page, lastTtsVol); if (r?.ok) lastTtsVol = r.vol; console.log('[music] 読み上げ初期音量', lastTtsVol); } catch {}

  try { await agora.drainInbox(page); } catch {}   // join前の残/エコー一掃

  const st0 = loadState();
  const seen = new Set(st0.seen);
  console.log('[music] 稼働開始（純音楽BOT・YouTube）。/h でヘルプ');

  // 起動時テスト再生（任意）
  if (process.env.YAY_TEST_PLAY && joined.rtc?.ok) {
    console.log('[music] ▶ TEST_PLAY:', process.env.YAY_TEST_PLAY);
    console.log('[music] 結果:', await handleCommand('/play ' + process.env.YAY_TEST_PLAY));
  }
  if (process.env.YAY_AUTO_LIVE && joined.rtc?.ok) {
    console.log('[music] ▶ AUTO_LIVE:', process.env.YAY_AUTO_LIVE);
    console.log('[music] 結果:', await handleCommand('/lv ' + process.env.YAY_AUTO_LIVE));
  }

  for (;;) {
    // キュー自動送り: 再生が止まっててキューがあれば次を流す
    if (!starting) {
      try {
        const st = await agora.status(page);
        if (!st?.nowPlaying) {
          if (queue.length) {
            const next = queue.shift();
            if (queueRepeat) queue.push(next);   // リピートON: 流した曲を末尾へ戻して循環
            const r = await startTrack(next); console.log('  ▶ next:', r, queueRepeat ? '(repeat)' : '');
          }
          else if (nowQuery && nowQuery !== 'live') { nowQuery = null; }
        }
      } catch {}
    }

    // 入退室の読み上げ（名簿差分→挨拶。throttle は関数内）
    try { await pollMembersAndDiff(); } catch (e) { console.error('greet poll', e.message); }
    try { await drainJingle(); } catch (e) { console.error('greet drain', e.message); }

    let raw = [];
    try { raw = await agora.drainInbox(page); } catch (e) { console.error('drain err', e.message); }
    const msgs = raw.map(parseMsg).filter((m) => m.text);
    const fresh = msgs.filter((m) => !seen.has(m.id) && m.author !== SELF_RTM);
    fresh.forEach((m) => seen.add(m.id));

    if (fresh.length) {
      const ts = new Date().toLocaleTimeString('ja-JP');
      for (const m of fresh) {
        console.log(`[${ts}] ${m.author}: ${m.text}`);
        // 1メッセージに複数コマンド行（改行区切り）があれば順に実行し、応答をまとめる。
        let mr = await runCommands(m.text);
        // 自然言語の音楽指示（通話の全員）。コマンド以外でだけ試す。
        if (mr === null && !/^[!\/]/.test(m.text)) {
          const nl = nlToCommand(m.text);
          if (nl) { console.log('  🗣→cmd', nl); mr = await handleCommand(nl); }
        }
        if (mr) { await sendYayChat(page, mr).catch((e) => console.error('send', e.message)); console.log('  ♪', mr); }
      }
      saveState({ seen: [...seen].slice(-2000) });
    }
    await sleep(CONFIG.pollMs);
  }
}

process.on('unhandledRejection', (e) => console.error('unhandledRejection:', e?.message || e));
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => process.exit(0));
(async () => {
  for (;;) {
    try { await main(); }
    catch (e) { console.error('[music] 落ちた→5秒後再起動:', e.message); await sleep(5000); }
  }
})();
