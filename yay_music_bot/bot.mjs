// yay_music_bot — 純音楽BOT（Yay 通話 / YouTube → Agora RTC publish）。
// yay_bot（究の個人用フル機能bot）から分離した独立PJ。会話/人格/聴取/開発ツールは持たない。
// 唯一の声機能＝入退室の読み上げ（名前を短く言うだけ・LLM不使用＝コンテキスト消費ゼロ）。
// 録音は持つ（究指示 2026-06-11 で yay_bot から復帰移植。常時録音→mp3保存、/rec で操作）。
//
// 流れ:
//   1) yay_api.py で通話creds(agora_channel/agora_token/rtm_token/uid)を取得（待ち受け→自動join）
//   2) 制御下Chromiumで agora_client.html を開き Agoraチャンネルへ join
//   3) RTM受信をpollingし、音楽コマンド(/play 等)と自然言語(「○○かけて」)を実行
//   4) /play は yt-dlp で解決→RTC publish。キューと自動送り対応。
//
// 起動: node bot.mjs            （現在参加中の通話を自動発見）
//      YAY_CALL_ID=<id> node bot.mjs （call_id 明示）
import { readFileSync, writeFileSync, existsSync, mkdirSync, statSync, readdirSync, appendFileSync, unlinkSync } from 'node:fs';
import { appendFile } from 'node:fs/promises';
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
// 追従先の制限: 究(WATCH_UID)が「自分で立てた枠」だけに入る。他人の枠にゲスト参加してても追わない。
//   判定 = その通話の post 作成者(host_uid) が究のuidと一致するか。
//   明示ピン(YAY_CALL_ID)時や watch 未設定時は制限しない。YAY_FOLLOW_ANY=1 で無効化（昔の挙動）。
const WATCH_UID = process.env.YAY_WATCH_UID ? String(process.env.YAY_WATCH_UID) : null;
function isOwnRoom(c) {
  if (!WATCH_UID || process.env.YAY_CALL_ID || process.env.YAY_FOLLOW_ANY === '1') return true;
  return String(c?.host_uid ?? '') === WATCH_UID;
}
function runApiJson(args, timeout = 30000) {
  return new Promise((resolve, reject) => {
    execFile(PY, [API, ...args], { timeout }, (err, stdout, stderr) => {
      const lines = (stdout || '').trim().split('\n').filter(Boolean);
      let json = null;
      for (let i = lines.length - 1; i >= 0; i--) { try { json = JSON.parse(lines[i]); break; } catch {} }
      if (!json) return reject(new Error('API JSON 解析不可: ' + (stderr || stdout || err?.message)));
      resolve(json);
    });
  });
}
function fetchCreds() {
  const args = process.env.YAY_CALL_ID ? ['creds', String(process.env.YAY_CALL_ID)] : ['active', DISCOVER_UID];
  return runApiJson(args);
}
// 直近に入ってた究の枠への復帰用フォールバック。
//   Yay の active は「ホスト自身の枠」を返さないことがある→究が自分で立てた枠に居るのに発見できない。
//   そこで直近 join した call_id を覚えておき、active が空振りした時、その枠にまだ究が居れば creds を取り直す。
const LASTCALL_FILE = '.yay_lastcall';
function saveLastCall(id) { try { if (id) writeFileSync(LASTCALL_FILE, JSON.stringify({ id: String(id), at: Date.now() })); } catch {} }
async function fallbackToLastCall() {
  if (process.env.YAY_CALL_ID || !WATCH_UID) return null;
  let last; try { last = JSON.parse(readFileSync(LASTCALL_FILE, 'utf8')); } catch { return null; }
  if (!last?.id || Date.now() - (last.at || 0) > 12 * 3600 * 1000) return null;   // 12h より古いものは捨てる
  // その枠にまだ究が居るか確認（究不在の他人だけの枠には入らない＝「俺の枠だけ」維持）
  let mem; try { mem = await runApiJson(['members', String(last.id)], 20000); } catch { return null; }
  const here = (mem?.users || []).some((u) => String(u.id ?? '') === WATCH_UID);
  if (!here) return null;
  let cr; try { cr = await runApiJson(['creds', String(last.id)], 30000); } catch { return null; }
  if (cr?.ok) { console.log(`[music] activeが究の枠を返さない→直近の枠(${last.id})に究在室を確認し復帰`); return cr; }
  return null;
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
  // Yay のチャットメッセージ id は "<送信者のYay uid>_<ts>" 形式。先頭を送信者uidとして取り出す。
  const senderUid = msgId ? String(msgId).split('_')[0] : null;
  return { id: msgId ? `id:${msgId}` : `${author}|${m.ts}|${text}`, author, senderUid, text, type };
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
let queue = [];        // 未再生キュー（確定URL or query文字列）
const titleCache = new Map();  // URL → 正式タイトル（先行検索で確定したものを表示用に保持）
let nowQuery = null;   // 再生中の曲名/ラベル
let starting = false;  // 多重起動ガード
let lastVol = Number(process.env.YAY_MUSIC_VOL || 3);   // 音楽の初期音量（究指示 2026-06-12 既定3）
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
// キュー表示用ラベル（先行検索で確定した正式タイトルがあればそれ、無ければURL短縮/曲名そのまま）。
function qLabel(s) {
  const cached = titleCache.get(s);
  if (cached) return cached;
  if (!/^https?:\/\//i.test(s)) return s;
  const m = s.match(/[?&]v=([\w-]{6,})/) || s.match(/youtu\.be\/([\w-]{6,})/);
  return m ? `▶ ${m[1]}` : s.slice(0, 48);
}

// ===== 録音（通話まるごと → webm 逐次追記 → 停止/離脱で mp3 128kbps 変換）=====
// yay_bot から移植（究指示 2026-06-11「録音機能戻して」）。join 直後に自動開始、毎ループで
// チャンクをファイルへ追記。ページ層（agora_client.html の startRecord 等）は最初から同梱済で
// bot.mjs の配線だけ欠けていた。保存先 recordings/ は git 管理外。
const REC_DIR = fileURLToPath(new URL('./recordings', import.meta.url));
let recState = null;   // { webmPath, mp3Path, startedAt, active }

const ts2 = () => { const d = new Date(); const p = (n) => String(n).padStart(2, '0'); return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`; };

async function startCallRecording(callId) {
  if (recState?.active) return;
  try {
    mkdirSync(REC_DIR, { recursive: true });
    const base = `yay_${callId || 'call'}_${ts2()}`;
    const webmPath = `${REC_DIR}/${base}.webm`;
    const r = await agora.startRecord(page);
    if (!r?.ok) { console.error('[rec] 開始失敗', r?.reason); return; }
    recState = { webmPath, mp3Path: `${REC_DIR}/${base}.mp3`, startedAt: Date.now(), active: true };
    console.log('[rec] ● 録音開始', webmPath);
  } catch (e) { console.error('[rec] start err', e.message); }
}

// 録音チャンクのファイル追記。音楽配信と並走するため (1)同期 appendFileSync を使わず
//   非同期 appendFile（event loop を固めない）、(2)毎周回でなく間引いて CDP の base64 大転送を
//   減らす（音楽ページへの負荷＝ぶつぶつ要因を抑制）。チャンクはページ側に溜まり停止時に全回収。
let lastRecDrainAt = 0;
const REC_DRAIN_MS = Number(process.env.YAY_REC_DRAIN_MS || 6000);
async function drainRecToFile(force = false) {
  if (!recState?.active) return;
  if (!force && Date.now() - lastRecDrainAt < REC_DRAIN_MS) return;
  lastRecDrainAt = Date.now();
  try {
    const chunks = await agora.drainRecChunks(page);
    for (const b64 of chunks) {
      try { await appendFile(recState.webmPath, Buffer.from(b64, 'base64')); }
      catch (e) { console.error('[rec] append', e.message); }
    }
  } catch (e) { console.error('[rec] drain', e.message); }
}

// webm → mp3 非ブロッキング（execFileSync だと大ファイルで event loop が固まり音楽がぶつぶつになる）。
//   逐次追記の未finalize webm でも ffmpeg は全音声を回収できる（"File ended prematurely" は無害）。
function convertToMp3Async(webmPath, mp3Path) {
  return new Promise((resolve) => {
    execFile('ffmpeg', ['-y', '-i', webmPath, '-c:a', 'libmp3lame', '-b:a', '128k', mp3Path],
      { timeout: 600000 }, (err) => {
        if (!existsSync(mp3Path)) return resolve({ ok: false, reason: err?.message || 'no output' });
        try { resolve({ ok: true, kb: Math.round(statSync(mp3Path).size / 1024) }); }
        catch { resolve({ ok: false, reason: 'stat失敗' }); }
      });
  });
}

// 取りこぼし回収（失敗しない仕組みの核）: recordings/ の webm のうち mp3 が無い/空のものを全部 mp3 化。
//   起動のたびに走らせる＝前回クラッシュ/kill で mp3 化されなかった分を確実に救う（冪等）。
//   録音中の webm は触らない。非ブロッキングで1件ずつ（CPU/負荷を抑える）。
async function recoverOrphanRecordings() {
  try {
    mkdirSync(REC_DIR, { recursive: true });
    const webms = readdirSync(REC_DIR).filter((f) => f.endsWith('.webm'));
    const orphans = webms.filter((f) => {
      const webm = `${REC_DIR}/${f}`;
      const mp3 = `${REC_DIR}/${f.replace(/\.webm$/, '.mp3')}`;
      if (recState?.active && recState.webmPath === webm) return false;   // 録音中のは対象外
      try { if (statSync(webm).size < 1024) return false; } catch { return false; }  // 空webmは無視
      return !existsSync(mp3) || (() => { try { return statSync(mp3).size < 1024; } catch { return true; } })();
    });
    if (!orphans.length) { console.log('[rec] ✓ mp3化漏れなし（孤児webm 0件）'); return; }
    console.log(`[rec] 🔧 取りこぼし回収: 孤児webm ${orphans.length}件を mp3 化（前回クラッシュ/kill分）`);
    for (const f of orphans) {
      const r = await convertToMp3Async(`${REC_DIR}/${f}`, `${REC_DIR}/${f.replace(/\.webm$/, '.mp3')}`);
      console.log(r.ok ? `[rec]   ✓ ${f} → mp3 (${r.kb}KB)` : `[rec]   ✗ ${f}: ${r.reason}`);
    }
    console.log('[rec] 回収完了');
  } catch (e) { console.error('[rec] orphan sweep err', e.message); }
}

// 録音停止＋mp3化（/bye・bot停止・/rec stop で呼ぶ）。
async function stopCallRecording() {
  if (!recState?.active) return null;
  recState.active = false;
  try {
    const r = await agora.stopRecord(page);
    for (const b64 of (r?.chunks || [])) { try { appendFileSync(recState.webmPath, Buffer.from(b64, 'base64')); } catch {} }
  } catch (e) { console.error('[rec] stop', e.message); }
  const mins = Math.round((Date.now() - recState.startedAt) / 60000);
  const conv = await convertToMp3Async(recState.webmPath, recState.mp3Path);
  const out = { ...recState, mins, conv };
  console.log('[rec] ■ 停止→mp3', conv.ok ? `${recState.mp3Path} (${conv.kb}KB)` : 'ffmpeg失敗:' + conv.reason);
  recState = null;
  return out;
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
// あいさつ口調はモードで切替（kiritan=クール敬語 / zunda=〜なのだ）。greetWord は時間帯の挨拶語のみ。
function greetWord() {
  const h = new Date().getHours();
  if (h >= 5 && h < 11) return voiceMode === 'zunda' ? 'おはよう' : 'おはようございます';
  if (h >= 11 && h < 18) return 'こんにちは';
  return 'こんばんは';
}
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
function enGreetWord() {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return 'Good morning';
  if (h >= 12 && h < 18) return 'Good afternoon';
  return 'Good evening';
}
function jingleLine({ kind, nick, returning }) {
  const g = greetWord();
  if (voiceMode === 'katakoto') {
    const who = nick || 'ミナサン';
    const h = new Date().getHours();
    const kg = (h >= 5 && h < 11) ? 'オハヨー' : (h < 18 ? 'コンニチワ' : 'コンバンワ');
    if (kind === 'leave') return pick([`${who}、マタネー！`, `${who}、バイバーイ！`, `オー、${who}、イッチャウ ノ？`]);
    if (returning) return pick([`オー！${who}、カエッテキタ ネー！`, `${who}、オカエリ ネー！`]);
    return pick([`${who}、${kg}！ヨウコソ ネー！`, `オー！${who}、キタ ネー！`, `${who}、イラッシャーイ！`]);
  }
  if (voiceMode === 'english') {
    const who = nick || 'everyone';
    if (kind === 'leave') return pick([`Goodbye, ${who}.`, `See you, ${who}.`, `Take care, ${who}.`]);
    if (returning) return pick([`Welcome back, ${who}.`, `Good to see you again, ${who}.`]);
    return pick([`${enGreetWord()}, ${who}. Welcome.`, `Welcome, ${who}.`, `${enGreetWord()}, ${who}.`]);
  }
  if (voiceMode === 'zunda') {
    const who = nick || '誰か';
    if (kind === 'leave') return pick([`${who}、またなのだ！`, `${who}、ばいばいなのだ！`, `${who}、お疲れなのだ！`]);
    if (returning) return pick([`${who}、おかえりなのだ！`, `おっ、${who}が戻ってきたのだ！`]);
    return pick([`${who}、${g}！いらっしゃいなのだ！`, `${g}！${who}、よく来たのだ！`, `${who}、いらっしゃいなのだ！`]);
  }
  const who = (nick || '誰か') + 'さん';
  if (kind === 'leave') return pick([`${who}、お疲れさまでした`, `${who}、またお越しください`, `${who}、またお会いしましょう`]);
  if (returning) return pick([`${who}、おかえりなさいませ`, `${who}、お戻りですね`, `${who}、おかえりなさい`]);
  return pick([`${who}、${g}。いらっしゃいませ`, `${who}、${g}。ようこそお越しくださいました`, `${g}、${who}`, `${who}、ようこそ`]);
}
// 複数人が同時に来た/去った時は1メッセージにまとめて全員へ挨拶（究指示2026-06-14「一人にしか行かない」修正）。
function nameListEn(ns) { return ns.length <= 1 ? (ns[0] || 'everyone') : ns.slice(0, -1).join(', ') + ' and ' + ns[ns.length - 1]; }
function jingleLineMulti(kind, items) {
  const ns = items.map((i) => i.nick).filter(Boolean);
  if (ns.length <= 1) return jingleLine(items[0]);
  const g = greetWord();
  if (voiceMode === 'katakoto') {
    const nl = ns.join('、');
    return kind === 'leave' ? `${nl}、マタネー！` : `${nl}、ヨウコソ ネー！`;
  }
  if (voiceMode === 'english') {
    const nl = nameListEn(ns);
    return kind === 'leave' ? `Goodbye, ${nl}.` : `${enGreetWord()}, ${nl}. Welcome.`;
  }
  if (voiceMode === 'zunda') {
    const nl = ns.join('、');
    return kind === 'leave' ? `${nl}、またなのだ！` : `${nl}、${g}！いらっしゃいなのだ！`;
  }
  const nl = ns.map((n) => `${n}さん`).join('、');
  return kind === 'leave' ? `${nl}、お疲れさまでした` : `${nl}、${g}。いらっしゃいませ`;
}
function inQuietHours() {
  const qh = JC().quietHours;
  if (!Array.isArray(qh) || qh.length !== 2) return false;
  const h = new Date().getHours(); const [a, b] = qh;
  return a <= b ? (h >= a && h < b) : (h >= a || h < b);   // 跨ぎ(例: 23-7)も対応
}
// 声＋口調モード（究指示2026-06-14）。kiritan=東北きりたん×クール敬語 / zunda=ずんだもん×〜なのだ。
//   `.yay_mode` ファイルに永続。/voice コマンドで再起動なしにトグル可。
const MODE_FILE = '.yay_mode';
const MODE_VOICE = { kiritan: 'kiritan', zunda: 'zundamon', english: 'english', katakoto: 'english' };   // katakoto=Daniel声でカタコト日本語
let voiceMode = (() => { try { const m = readFileSync(MODE_FILE, 'utf8').trim(); return MODE_VOICE[m] ? m : 'english'; } catch { return 'english'; } })();   // 既定=English(究指示2026-06-14)
function setVoiceMode(m) { if (!MODE_VOICE[m]) return false; voiceMode = m; try { writeFileSync(MODE_FILE, m); } catch {} return true; }
// TTSボイス: モード(kiritan/zunda/english)の声。YAY_VOICE で明示上書き可。
const VOICE_KEY = () => process.env.YAY_VOICE || MODE_VOICE[voiceMode] || 'say_default';
// 読み上げ用テキスト整形: englishモードでは日本語を機械的ローマ字化して Daniel に読ませる（チャット文字は別＝原文のまま）。
async function spokenForm(text) {
  if (voiceMode !== 'english' && voiceMode !== 'katakoto') return text;   // Daniel声は日本語をローマ字化して読む
  try { return await tts.toRomaji(text); } catch { return text; }
}
// あいさつを声で（音楽を止めず ttsGain に乗せ自動ダッキング）。quietHours/voice=false なら無声。
async function sayJingle(text) {
  if (JC().voice === false || inQuietHours()) return;
  try {
    const r = await tts.speak(await spokenForm(text), { voice: VOICE_KEY() });
    if (!r.ok || !r.file) return;
    await agora.playTTS(page, agora.fileUrl(fileBase, r.file)).catch((e) => console.error('[greet] playTTS', e.message));
  } catch (e) { console.error('[greet] say', e.message); }
}
// 究が書いた文字（/say・送信箱・究の発言読み上げ）は常に東北きりたんで読む（究指示2026-06-14）。
// あいさつ(sayJingle)はモードの声のまま。きりたんは日本語をそのまま読むのでローマ字化しない。
const USER_VOICE = 'kiritan';
async function speakText(text) {
  const t = String(text || '').trim();
  if (!t) return;
  try {
    const r = await tts.speak(t, { voice: USER_VOICE });
    if (r.ok && r.file) await agora.playTTS(page, agora.fileUrl(fileBase, r.file)).catch((e) => console.error('[say] playTTS', e.message));
  } catch (e) { console.error('[say] speak', e.message); }
}
// Yay側参加の見張り: Yay はしばらくすると bot の参加を名簿から落とすことがある。
// その間アプリ上で bot が見えず chat も表示されない（Agora の RTC/RTM は生きてるので
// こちらからは受信できてしまい気づけない）。名簿に自分が居なければ参加し直す。
let lastRejoinAt = 0;
function yayRejoin(callId) {
  return new Promise((resolve) => {
    execFile(PY, [API, 'join', String(callId)], { timeout: 20000 }, (err, stdout) => {
      const lines = (stdout || '').trim().split('\n').filter(Boolean);
      for (let i = lines.length - 1; i >= 0; i--) { try { return resolve(JSON.parse(lines[i])); } catch {} }
      resolve({ ok: false });
    });
  });
}
// 追従: 究(YAY_WATCH_UID)が別の通話へ移ったら検知し、再起動して新しい通話を再発見する。
//   生のチャンネル切替よりプロセス再起動（supervise が立て直し→起動時discovery）の方が堅い。
//   明示ピン(YAY_CALL_ID)時や watch 未設定時は追従しない。
let lastFollowAt = 0;
async function followWatchedUser() {
  if (process.env.YAY_CALL_ID || !process.env.YAY_WATCH_UID) return;
  const now = Date.now();
  if (now - lastFollowAt < (CONFIG.followMs || 30000)) return;
  lastFollowAt = now;
  let cur;
  try { cur = await fetchCreds(); } catch { return; }   // active 9714060（究の現在通話）
  if (!cur || !cur.ok) return;                           // 究が通話に居ない/取得失敗 → 何もしない
  if (!isOwnRoom(cur)) return;                           // 究が他人の枠に居るだけ → 追わない
  const here = String(creds?.conference_id || '');
  const there = String(cur.conference_id || '');
  if (there && here && there !== here) {
    console.log(`[music] 究が別の通話へ移動 (${here}→${there}) → 追従のため再起動`);
    try { await agora.leave(page); } catch {}
    process.exit(0);   // supervise が5秒で立て直し、起動時discoveryで新通話へ入る
  }
}
// 名簿ポーリング＋差分（throttle はここで持つ。loop から毎周回呼んでよい）。
// あいさつOFFでも回す（Yay参加見張りはあいさつと独立に必要）。
async function pollMembersAndDiff() {
  const callId = process.env.YAY_CALL_ID || creds?.conference_id;
  if (!callId) return;
  const now = Date.now();
  if (now - lastMemberPollAt < (JC().pollMs || 12000)) return;
  lastMemberPollAt = now;
  let res; try { res = await fetchMembers(callId); } catch { return; }
  if (!res?.ok || !Array.isArray(res.users)) return;
  const selfId = String(SELF_UID);
  if (!res.users.some((u) => String(u.id ?? '') === selfId) && now - lastRejoinAt > 60000) {
    lastRejoinAt = now;
    const r = await yayRejoin(callId);
    console.log(r?.ok ? '[music] ↻ Yay参加が名簿から落ちてたので参加し直した' : '[music] ⚠ Yay再参加失敗（次の周回で再試行）');
  }
  const seenNow = new Set();
  for (const u of res.users) {
    const id = String(u.id ?? '');
    if (!id || id === selfId) continue;     // 自分(Emo Music)は除外
    seenNow.add(id);
    const prev = roster.get(id);
    const nick = u.nickname || prev?.nick || null;
    if (!prev || !prev.present) {
      if (memberSeeded && jingleOn) {
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
      if (memberSeeded && jingleOn) jingleQueue.push({ kind: 'leave', nick: info.nick, returning: false });
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
  lastJingleAt = now;
  // 溜まってる入退室を全部取り、同時のものは join/leave ごとに1メッセージへまとめる。
  const batch = jingleQueue.splice(0, jingleQueue.length);
  for (const [kind, items] of [['join', batch.filter((j) => j.kind === 'join')], ['leave', batch.filter((j) => j.kind === 'leave')]]) {
    if (!items.length) continue;
    const line = jingleLineMulti(kind, items);
    try { await sendYayChat(page, line); } catch (e) { console.error('[greet] chat', e.message); }
    await sayJingle(line);
    console.log('  greet:', line);
  }
}
function presentCount() { return [...roster.values()].filter((r) => r.present).length; }

// canonical → [aliases]（`/` でも `!` でも発火）。音楽コマンドのみ。
const CMD = {
  help:   ['help', 'h', '?'],
  play:   ['play', 'p', 'pl'],
  queue:  ['queue', 'q', 'add'],
  plsearch:['plist', 'plsearch', 'pls', 'プレイリスト', '再生リスト'],  // キーワードでプレイリストを検索→展開してキューへ
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
  rec:    ['rec', 'record', '録音'],         // 録音 状態/保存/停止/開始
  say:    ['say', '言って', '送信', 'いって'],   // 任意のテキストを通話チャットへ送る（究の代弁）
  voice:  ['voice', 'mode', 'モード', '声'],      // 声＋口調モード切替（kiritan / zunda）。再起動不要でトグル
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
      '📃 /plist 名前 プレイリスト検索（「○○のプレイリストかけて」でも可）',
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
    '🔴 /rec 録音状態  💾 /rec save 区切り保存  ⏹ /rec stop 停止',
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
  if (/録音.*(止め|停止|終わ|やめ|オフ)/.test(t)) return '/rec stop';
  if (/(ここまで|今まで).*(保存|録音)|録音.*保存/.test(t)) return '/rec save';
  if (/録音(して|開始|始め|オン|を?しといて)?$/.test(t) || /録音.*(して|開始|始め|オン)/.test(t)) return '/rec on';
  if (/(一時停止|ポーズ|ちょっと止め)/.test(t)) return '/pause';
  if (/(再開|続きから|戻して再生)/.test(t)) return '/resume';
  if (/(止めて|停めて|ストップ|止めろ|停止|音楽.*消)/.test(t)) return '/stop';
  if (/(次の?曲|次に?して|次いって|スキップ|とばして|飛ばして|チェンジして)/.test(t)) return '/skip';
  if ((m = t.match(/(?:音量|ボリューム|ボリュ)\D*?(\d{1,3}(?:\.\d+)?)/))) return `/vol ${m[1]}`;
  if (/(?:音量|ボリューム|音)/.test(t) && /(上げ|大きく|でかく|あげて|うるさ)/.test(t)) return '/volup';
  if (/(?:音量|ボリューム|音)/.test(t) && /(下げ|小さく|さげて|ちいさ|静か|絞)/.test(t)) return '/voldown';
  // 「○○(の)プレイリスト(を)かけて」→ プレイリスト検索。
  //   ※ play動詞の "プレイ" が "プレイリスト" に誤爆するので、こちらを先に・専用パターンで判定。
  const plm = t.match(/^(.*?)(?:の|を)?\s*(?:プレイリスト|playlist|再生リスト)\s*(?:を|で)?\s*(?:かけて|流して|再生して|プレイして|かけろ|流せ|流す|再生|聴きたい|聞きたい|して|ちょうだい|頂戴)?\s*$/i);
  if (plm && plm[1] && plm[1].trim()) return `/plist ${plm[1].trim()}`;
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
      case 'say': { if (!q) return '何を言う？（例: /say へーのばか）'; speakText(q); return q; }   // 読み上げ＋文字（返り値がチャットへ）
      case 'voice': {   // 声＋口調モード切替（再起動なしで即反映）
        const a = q.toLowerCase();
        const names = { kiritan: '東北きりたんモード', zunda: 'ずんだもんモード', english: 'Englishモード(Daniel)', katakoto: 'カタコトモード(Daniel)' };
        if (!a) return `🎙 現在: ${names[voiceMode]}（切替: /voice kiritan | zunda | english | katakoto）`;
        if (/zunda|ずんだ/.test(a)) { setVoiceMode('zunda'); return 'ずんだもんモードに切り替えたのだ！'; }
        if (/kiri|きりたん/.test(a)) { setVoiceMode('kiritan'); return '東北きりたんモードに切り替えました'; }
        if (/kata|カタコト|片言/.test(a)) { setVoiceMode('katakoto'); return 'オー！カタコトモード ネ！'; }
        if (/eng|英語|daniel/.test(a)) { setVoiceMode('english'); return 'Switched to English mode.'; }
        return '使い方: /voice kiritan | zunda | english | katakoto';
      }
      case 'play':
      case 'queue': {
        if (!q) return renderQueue();           // 引数なし = 番号付き一覧
        const songs = splitSongs(q);            // カンマ/読点/改行区切りで複数曲対応
        // 各入力を「確定アイテム {url,title}」へ先行解決してからキューに入れる。
        //   プレイリストURL → 展開（title付き）。曲名/動画URL → searchTrack で検索し正式タイトル確定。
        const items = [];   // {url, title}
        let note = '';
        for (const s of songs) {
          if (isPlaylistUrl(s)) {
            try {
              const ex = await music.expandPlaylist(s, { limit: PLAYLIST_LIMIT });
              if (ex.length) { items.push(...ex); note += `📃 プレイリスト展開: ${ex.length}曲\n`; }
              else note += '⚠ プレイリストが空\n';
            } catch (e) { console.error('playlist expand', e.message); note += '⚠ プレイリスト展開失敗\n'; }
          } else {
            const hit = await music.searchTrack(s);   // ← キュー前に検索して曲名確認
            if (hit) items.push(hit);
            else note += `❌ 見つからず: ${s}\n`;
          }
        }
        if (!items.length) return (note || notFoundMsg(q)).trim();
        for (const it of items) titleCache.set(it.url, it.title);   // 表示用に正式タイトル保持
        // 空いてれば先頭を即再生、残りをキュー。再生中なら全部キュー末尾へ。
        let started = null; const added = [];
        for (const it of items) {
          if (!nowQuery && !starting && !started) {
            const r = await startTrack(it.url);
            if (r.ok) started = it; else { queue.push(it.url); added.push(it); }
          } else { queue.push(it.url); added.push(it); }
        }
        // 「今流れてる」は startTrack が "🎵 タイトル" を別途送る。ここではキュー結果だけ返す。
        if (added.length === 1 && !started) return `${note}➕ キューに追加(${queue.length}): ${added[0].title}`.trim();
        if (added.length) return `${note}➕ ${added.length}曲をキューに追加\n${renderQueue()}`.trim();
        return note.trim() || null;
      }
      case 'plsearch': {
        if (!q) return '🔎 プレイリスト名を指定（例: /plist 作業用BGM jazz）';
        let pl;
        try { pl = await music.searchPlaylist(q); } catch (e) { console.error('plsearch', e.message); }
        if (!pl) return `❌ プレイリストが見つかりません: ${q}`;
        let ex = [];
        try { ex = await music.expandPlaylist(pl.url, { limit: PLAYLIST_LIMIT }); } catch (e) { console.error('pl expand', e.message); }
        if (!ex.length) return `❌ 展開できませんでした: ${pl.title}`;
        for (const it of ex) titleCache.set(it.url, it.title);
        let started = null; const added = [];
        for (const it of ex) {
          if (!nowQuery && !starting && !started) {
            const r = await startTrack(it.url);
            if (r.ok) started = it; else { queue.push(it.url); added.push(it); }
          } else { queue.push(it.url); added.push(it); }
        }
        return `📃 プレイリスト「${pl.title}」${ex.length}曲\n➕ ${added.length}曲をキューに追加\n${renderQueue()}`.trim();
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
      case 'rec': {
        if (/^(stop|off|止め|終わ|停止|オフ)/.test(q)) {
          const r = await stopCallRecording();
          return r ? (r.conv.ok ? `■ 録音停止→mp3保存(${r.mins}分/${r.conv.kb}KB): ${r.mp3Path.split('/').pop()}` : `■ 停止したがmp3変換失敗: ${r.conv.reason}`) : '録音してない';
        }
        if (/^(save|保存|区切|スナップ|ここまで)/.test(q)) {
          if (!recState?.active) return '録音してない';
          await drainRecToFile(true);   // 間引きを無視して今ある分を確実に書き出してからスナップ
          const snap = recState.mp3Path.replace(/\.mp3$/, `_snap_${ts2()}.mp3`);
          const c = await convertToMp3Async(recState.webmPath, snap);   // 非ブロッキング＝音楽を固めない
          return c.ok ? `💾 ここまでをmp3保存(${c.kb}KB): ${snap.split('/').pop()}（録音継続中）` : `mp3変換失敗: ${c.reason}`;
        }
        if (/^(on|start|開始|再開|始め)/.test(q) || (!q && !recState?.active)) {
          await startCallRecording(process.env.YAY_CALL_ID || creds?.conference_id || 'call');
          return recState?.active ? '● 録音開始' : '録音開始に失敗';
        }
        const st = await agora.recStatus(page);
        return recState?.active ? `🔴 録音中（${Math.round((Date.now() - recState.startedAt) / 60000)}分 / 音源${st?.sources ?? '?'}）: ${recState.webmPath.split('/').pop()}` : '⚪ 録音停止中（/rec on で開始）';
      }
      case 'leave': await stopCallRecording(); await agora.leave(page); nowQuery = null; queue = []; return '👋 通話から抜けた（録音はmp3化して保存）';
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
  recoverOrphanRecordings();   // await しない＝待ち受けと並行で前回分を mp3 化
  console.log('[music] 通話待ち受け開始（通話に入ったら自動参加）…');
  for (;;) {
    creds = await fetchCreds().catch((e) => ({ ok: false, error: e.message }));
    if (creds && creds.ok) {
      if (isOwnRoom(creds)) break;
      console.log(`[music] 究の枠ではない通話 (host=${creds.host_uid}) → 入らず待機`);
      creds = { ok: false, error: 'not own room' };
    } else {
      // active が究のホスト枠を返さない時の保険: 直近の自分の枠に究がまだ居れば復帰
      const fb = await fallbackToLastCall().catch(() => null);
      if (fb) { creds = fb; break; }
    }
    const reason = creds?.error || '不明';
    if (!/参加中の通話が無い|not own room/.test(String(reason))) console.log('[music] creds 取得待ち:', reason);
    await sleep(WAIT_MS);
  }
  console.log('[music] ✓ 通話発見→自動参加 channel=%s uid=%s', creds.channel, creds.uid);
  saveLastCall(creds.conference_id);   // 次回 active 空振り時の復帰用に覚えておく

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

  { const r = await agora.setMusicVolume(page, lastVol); if (r?.ok) lastVol = r.vol; console.log('[music] 初期音量', r?.vol ?? lastVol); }
  try { const r = await agora.setTtsVolume(page, lastTtsVol); if (r?.ok) lastTtsVol = r.vol; console.log('[music] 読み上げ初期音量', lastTtsVol); } catch {}

  try { await agora.drainInbox(page); } catch {}   // join前の残/エコー一掃

  const st0 = loadState();
  const seen = new Set(st0.seen);
  // 常時録音（究指示「常に録音して記録」、yay_bot と同じ既定。YAY_NO_REC=1 で無効化可）
  if (!process.env.YAY_NO_REC && joined.rtc?.ok) await startCallRecording(process.env.YAY_CALL_ID || creds?.conference_id);
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

    // 究が別の通話へ移ったら追従（throttle は関数内）
    try { await followWatchedUser(); } catch (e) { console.error('follow', e.message); }
    // 入退室の読み上げ（名簿差分→挨拶。throttle は関数内）＋ Yay参加見張り
    try { await pollMembersAndDiff(); } catch (e) { console.error('greet poll', e.message); }
    try { await drainJingle(); } catch (e) { console.error('greet drain', e.message); }

    // 外部送信箱: .yay_say にテキストを書くと、今入ってる通話チャットへ送って消す（究の代弁・再起動不要）
    try {
      if (existsSync('.yay_say')) {
        const t = readFileSync('.yay_say', 'utf8').trim();
        unlinkSync('.yay_say');
        for (const line of t.split('\n').map((s) => s.trim()).filter(Boolean)) {
          await sendYayChat(page, line).catch((e) => console.error('say send', e.message));
          await speakText(line);   // 読み上げも
          console.log('  📨 say:', line);
        }
      }
    } catch (e) { console.error('say outbox', e.message); }

    // 録音チャンクをファイルへ追記（常時・間引きは関数内）
    try { await drainRecToFile(); } catch (e) { console.error('rec drain', e.message); }

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
        // 究(WATCH_UID)の素のチャット（コマンド/音楽指示でない）は読み上げる
        else if (WATCH_UID && m.senderUid === WATCH_UID && !/^[!\/]/.test(m.text)) {
          await speakText(m.text); console.log('  🔊 究の発言を読み上げ:', m.text);
        }
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
