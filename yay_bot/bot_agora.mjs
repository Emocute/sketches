// yay_bot メインループ（全面API移行版 2026-06-03）。
// 旧: 実Chrome DOM(チャット) + BlackHole(音楽)。新: Agora RTC(音楽publisher) + RTM(チャット)。
//
// 流れ:
//   1) yay_api.py で通話creds(agora_channel/agora_token/rtm_token/uid)を取得
//   2) 制御下Chromiumで agora_client.html を開き Agoraチャンネルへ join
//   3) RTM受信をpollingしEmoCC返信→RTM送信。/play は yt-dlp解決→RTC publish
//
// 起動: node bot_agora.mjs            （現在参加中の通話を自動発見）
//      YAY_CALL_ID=<id> node bot_agora.mjs （call_id 明示）
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { CONFIG } from './config.mjs';
import { emoccReply, idleChatter, PERSONAS } from './lib/claude.mjs';
import * as agora from './lib/agora.mjs';
import * as music from './lib/music_agora.mjs';
import * as listen from './lib/listen.mjs';
import * as tts from './lib/tts.mjs';

const PY = fileURLToPath(new URL('./.venv/bin/python', import.meta.url));
const API = fileURLToPath(new URL('./yay_api.py', import.meta.url));
const SELF_UID = String(process.env.YAY_SELF_UID || '11320230');
// なりきり人格（YAY_PERSONA=zundamon 等が初期値）。チャットから /mode で実行時切替できる。
let personaKey = String(process.env.YAY_PERSONA || '').toLowerCase();
let personaSys = PERSONAS[personaKey] || undefined;
// 人格名の別名（日本語/略称 → canonical key）
const PERSONA_ALIAS = {
  zunda: 'zundamon', zundamon: 'zundamon', 'ずんだ': 'zundamon', 'ずんだもん': 'zundamon',
  natsuki: 'natsuki', 'なつき': 'natsuki', '夏希': 'natsuki', 'natsu': 'natsuki',
  succubus: 'succubus', 'succ': 'succubus', 'サキュバス': 'succubus', 'インキュバス': 'succubus',
};
// 自発おしゃべりのスケジュール（モジュールスコープ＝/mode から即発火させられる）
let lastActivityAt = 0, nextIdleAt = 0;
// 自発おしゃべりの間隔（中スパン）。YAY_IDLE_MIN/MAX 秒で上書き可。0=無効。
const IDLE_MIN_MS = Number(process.env.YAY_IDLE_MIN || 90) * 1000;
const IDLE_MAX_MS = Number(process.env.YAY_IDLE_MAX || 150) * 1000;
const IDLE_QUIET_MS = Number(process.env.YAY_IDLE_QUIET || 35) * 1000; // 直近の活動からこの時間空いたら独り言可
const idleSpan = () => IDLE_MIN_MS + Math.floor(Math.random() * Math.max(1, IDLE_MAX_MS - IDLE_MIN_MS));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const loadState = () => (existsSync(CONFIG.stateFile) ? JSON.parse(readFileSync(CONFIG.stateFile, 'utf8')) : { seen: [] });
const saveState = (s) => writeFileSync(CONFIG.stateFile, JSON.stringify(s, null, 2));

// yay_api.py を叩いて creds JSON を得る（最終行が JSON）。
//   発見uid = YAY_WATCH_UID(究本人のuid) があればそれ、無ければ SELF_UID。
//   別アカ運用時は WATCH_UID に究の通話を見張らせ、EmoCC(SELF) として join＝衝突せず共存。
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

// 連投ガード
let replyTimes = [], lastReplyAt = 0;
const canReply = () => {
  const now = Date.now();
  replyTimes = replyTimes.filter((t) => now - t < 60000);
  if (now - lastReplyAt < (CONFIG.replyCooldownMs || 0)) return false;
  return replyTimes.length < CONFIG.maxRepliesPerMin;
};
const markReplied = () => { const t = Date.now(); replyTimes.push(t); lastReplyAt = t; };

// RTM の生メッセージ → {id, author, text, type}。
// Yay通話チャットの実フォーマット（2026-06-03 生通話で発見）:
//   "<type> <JSON>"  例: `chat {"text":"...","created_at_seconds":1780492724,"id":"9714060_..."}`
//   先頭の型トークン（chat 等）を剥がしてから JSON を解いて本文(text)を拾う。
//   chat 以外（presence/system 等）は本文扱いしない。
function parseMsg(m) {
  let raw = m.message, author = String(m.publisher ?? '?');
  if (typeof raw !== 'string') { try { raw = JSON.stringify(raw); } catch { raw = String(raw); } }
  let type = 'chat', body = raw;
  const mt = /^(\w+)\s+([\[{][\s\S]*)$/.exec(raw);   // "chat {...}" の型プレフィックスを分離
  if (mt) { type = mt[1].toLowerCase(); body = mt[2]; }
  let text = body, msgId = null;
  try {
    const j = JSON.parse(body);
    if (j && typeof j === 'object') { text = j.text ?? j.message ?? j.content ?? j.body ?? ''; msgId = j.id ?? null; }
  } catch {}
  if (type !== 'chat') text = '';   // チャット以外は無視
  text = String(text || '').trim();
  return { id: msgId ? `id:${msgId}` : `${author}|${m.ts}|${text}`, author, text, type };
}

// Yayが表示できる送信エンベロープ。受信と同形式: `chat {"text","created_at_seconds","id"}`。
function yayEnvelope(text) {
  const now = Date.now();
  const payload = { text: String(text), created_at_seconds: Math.floor(now / 1000), id: `${SELF_UID}_${now}` };
  return 'chat ' + JSON.stringify(payload);
}
const sendYayChat = (p, text) => agora.sendChat(p, yayEnvelope(text));

let page, fileBase, creds;

// ===== コマンド体系（汎用・1〜2文字エイリアス対応）=====
let queue = [];        // 未再生キュー（query文字列）
let nowQuery = null;   // 再生中の曲名/ラベル
let starting = false;  // 多重起動ガード

// canonical → [aliases]（先頭が正式名）。`/` でも `!` でも発火。
const CMD = {
  help:   ['help', 'h'],
  helpshort: ['?'],
  play:   ['play', 'p'],
  queue:  ['queue', 'q', 'add'],
  skip:   ['skip', 's', 'next', 'n'],
  stop:   ['stop', 'x'],
  pause:  ['pause', 'ps'],
  resume: ['resume', 're', 'r'],
  vol:    ['vol', 'volume', 'v'],
  np:     ['np', 'now', 'nowplaying'],
  loop:   ['loop', 'l'],
  live:   ['live', 'lv'],
  dev:    ['devices', 'dev', 'd'],
  clear:  ['clear', 'cls', 'c'],
  ping:   ['ping', 'pi'],
  leave:  ['leave', 'bye'],
  mode:   ['mode', 'm', 'persona'],
  zunda:  ['zunda', 'ずんだ'],
  ears:   ['ears', 'listen', '耳', '聞く', 'kiku'],
  voice:  ['voice', 'yomi', 'tts', '読み', '読み上げ', '喋る', 'koe'],
  status: ['status', 'st', '状態', 'state'],
  qlist:  ['ql', 'qlist', 'きゅー', 'リスト'],
  qdel:   ['qd', 'qdel', 'rm', '消'],
  qup:    ['qu', 'qup', 'up', '上'],
  qdn:    ['qj', 'qdn', 'down', '下'],
};
const ALIAS = {}; for (const [k, vs] of Object.entries(CMD)) for (const v of vs) ALIAS[v] = k;
// トグル状態
let listening = false;  // 聞き取り（通話音声→文字起こし→返信）
let speaking = false;   // 読み上げ（返信のTTS＝ずんだもん声）

const onoff = (b) => (b ? '🟢ON' : '⚪OFF');
// いまの状態ブロック（/st と /h の冒頭で共用）
function statusBlock() {
  return [
    `🗣 読み上げ: ${onoff(speaking)}（ずんだもん声）`,
    `👂 聞き取り: ${onoff(listening)}`,
    `🎭 ずんだもん語尾: ${onoff(personaKey === 'zundamon')}`,
    nowQuery ? `🎵 再生中: ${nowQuery}` : '🎵 再生: なし',
  ].join('\n');
}
function renderHelpFull() {
  return [
    '🎧 EmoCC コマンド（詳細）',
    '― いまの状態 ―',
    statusBlock(),
    '― 切替（各コマンドでトグル / on・off 明示も可）―',
    '/voice（読）= 読み上げ。返信を自動でずんだもん声で喋る',
    '/ears（聞）= 聞き取り。通話の音声を文字起こし→自動返信',
    '/mode <モード> = 人格切替（zundamon/off 等）',
    '  ・/zunda = ずんだもん語尾 on/off',
    '― 音楽再生 ―',
    '/p <曲> = 再生開始',
    '/q <曲> = キューに追加（再生中なら直後に再生）',
    '/s（次）= スキップ / /x（停止）= 全停止',
    '/ps = 一時停止 / /r = 再開',
    '/v 0-100 = 音量設定（既定15）',
    '/np = 再生中の曲 / /l = 一曲ループ',
    '/lv [match] = システム音声配信（例: /lv mic）',
    '/c = キュー消去',
    '― キュー操作 ―',
    '/q / /qlist = キュー一覧（番号付き）',
    '/qd <N> = N番削除 / /qu <N> = N番を前へ / /qj <N> = N番を後ろへ',
    '― その他 ―',
    '/d = 音声入力デバイス一覧',
    '/st = 状態確認 / /h = 詳細ヘルプ / /? = 簡易ヘルプ',
    '/pi = ping / /bye = 通話から退出',
  ].join('\n');
}

function renderHelpShort() {
  return [
    '🎧 EmoCC コマンド（簡易）',
    '/voice /ears /mode <m> /zunda … 機能 on/off',
    '/p <曲> /q <曲> /s /x /ps /r /v <n> … 再生制御',
    '/np /l /lv /c … 再生情報・キュー',
    '/d /st /h /? /pi /bye … その他',
    '詳細: /h',
  ].join('\n');
}

function renderHelp() {
  return renderHelpFull();
}
// 返信を喋る（speaking時のみ）。TTS で WAV 生成 → Agora RTC に publish。
// 人格に応じたボイスパックを選択。
async function sayOut(text) {
  if (!speaking) return;
  try {
    // 人格に応じたボイス選択
    const voiceMap = {
      zundamon: 'zundamon',       // ずんだもん
      natsuki: 'akari',            // ナツキ → あかり（辛辣）
      succubus: 'zundamon_sad',   // サキュバス → 悲しい声（妖艶さ）
    };
    const voiceKey = voiceMap[personaKey] || undefined;
    const r = await tts.speak(text, { voice: voiceKey });
    if (!r.ok || !r.file) { console.error('tts: no file', r); return; }
    // WAV ファイルを Agora playUrl で再生（RTC publish）
    const url = agora.fileUrl(fileBase, r.file);
    await agora.playUrl(page, url).catch(() => {});  // 喋るのに失敗しても続行
  } catch (e) {
    console.error('sayOut err', e.message);
  }
}

// 人格の実行時切替（再起動不要）。ON にしたら起動直後と同じく一発目を即出す。
function setPersona(key) {
  personaKey = key || '';
  personaSys = personaKey ? PERSONAS[personaKey] : undefined;
  if (personaSys) { lastActivityAt = Date.now() - IDLE_QUIET_MS - 1; nextIdleAt = Date.now(); return `🎭 ${personaKey} モードON（自発おしゃべり ${IDLE_MIN_MS / 1000}〜${IDLE_MAX_MS / 1000}s）`; }
  return '🎭 通常モードに戻した（自発おしゃべりOFF）';
}

// 1曲を解決→publish（real-time）。解決した正式タイトルを「流す前」にチャットへ出す。
//   見つからなければ {ok:false,notfound:true} を返す（呼び出し側が ❌ で通知）。
async function startTrack(query) {
  starting = true;
  try {
    let r;
    try { r = await music.resolveStreamUrl(query); }
    catch (e) { console.error('  resolve失敗:', e.message); return { ok: false, notfound: true, query }; }
    const title = r.title || query;
    await sendYayChat(page, `🎵 ${title}`).catch(() => {});  // ★再生前に正式タイトルを通知
    await agora.playUrl(page, agora.streamUrl(fileBase, r.url));
    nowQuery = title;                                        // /np 表示も正式タイトルに
    return { ok: true, title };
  } finally { starting = false; }
}
const notFoundMsg = (q) => `❌ 見つかりませんでした: ${q}`;

// キューを番号付きで表示
function renderQueue() {
  const head = nowQuery ? `🎵 再生中: ${nowQuery}` : '🎵 再生: なし';
  if (!queue.length) return `${head}\n📜 キューは空`;
  const lines = queue.map((s, i) => `${i + 1}. ${s}`).join('\n');
  return `${head}\n📜 キュー(${queue.length})\n${lines}`;
}
// 番号引数（1始まり）→ 0始まりindex（範囲外は -1）
function qIndex(q) {
  const n = parseInt(q, 10);
  return (Number.isInteger(n) && n >= 1 && n <= queue.length) ? n - 1 : -1;
}

// テキスト → コマンド応答（コマンドでなければ null）
async function handleCommand(text) {
  const mm = String(text).match(/^\s*[!\/]\s*(\S+)\s*([\s\S]*)$/);
  if (!mm) return null;
  const cmd = ALIAS[mm[1].toLowerCase()];
  const q = (mm[2] || '').trim();
  if (!cmd) return null;
  try {
    switch (cmd) {
      case 'help': return renderHelp();
      case 'helpshort': return renderHelpShort();
      case 'status': return statusBlock();
      case 'ping': return '🏓 pong';
      case 'play': {
        if (!q) return '曲名を入れて（例: /p 曲名）';
        const r = await startTrack(q);          // 正式タイトルは startTrack が再生前に通知
        return r.ok ? null : notFoundMsg(q);
      }
      case 'queue':
        if (!q) return renderQueue();           // 引数なし = 番号付き一覧
        queue.push(q);
        if (!nowQuery && !starting) { const r = await startTrack(queue.shift()); return r.ok ? null : notFoundMsg(q); }
        return `➕ 追加(${queue.length}): ${q}\n` + renderQueue();
      case 'qlist': return renderQueue();
      case 'qdel': {
        if (!queue.length) return '📜 キューは空';
        const i = qIndex(q); if (i < 0) return `番号を指定して（1〜${queue.length}）例: /qd 2`;
        const [x] = queue.splice(i, 1);
        return `🗑 ${i + 1}. ${x} を削除\n` + renderQueue();
      }
      case 'qup': {
        const i = qIndex(q); if (i < 0) return `番号を指定して（1〜${queue.length}）例: /qu 2`;
        if (i === 0) return 'もう先頭だよ\n' + renderQueue();
        [queue[i - 1], queue[i]] = [queue[i], queue[i - 1]];
        return `⬆ ${i + 1}→${i} へ移動\n` + renderQueue();
      }
      case 'qdn': {
        const i = qIndex(q); if (i < 0) return `番号を指定して（1〜${queue.length}）例: /qj 2`;
        if (i === queue.length - 1) return 'もう末尾だよ\n' + renderQueue();
        [queue[i + 1], queue[i]] = [queue[i], queue[i + 1]];
        return `⬇ ${i + 1}→${i + 2} へ移動\n` + renderQueue();
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
      case 'vol': { const r = await agora.setMusicVolume(page, q); return r?.ok ? `🔊 音量 ${r.vol}` : '音量は 0〜100（例: /v 15）'; }
      case 'np': return nowQuery ? `🎵 再生中: ${nowQuery}${queue.length ? ` / 次(${queue.length}): ${queue.slice(0, 3).join(' / ')}` : ''}` : (queue.length ? `📜 キュー(${queue.length}): ${queue.slice(0, 5).join(' / ')}` : '何も流してない');
      case 'loop': { const r = await agora.setLoop(page); return r?.loop ? '🔁 一曲ループON（今の曲を繰り返す）' : '➡ 一曲ループOFF'; }
      case 'live': await agora.playLive(page, q || null); nowQuery = 'live'; return `▶ システム音声配信中${q ? '（' + q + '）' : ''}`;
      case 'dev': { const ds = await agora.listAudioInputs(page); return '🎤 入力: ' + (ds.map((d) => d.label).filter(Boolean).join(' / ') || 'なし'); }
      case 'leave': await agora.leave(page); nowQuery = null; queue = []; return '👋 通話から抜けた';
      case 'mode': {
        const want = q.toLowerCase();
        if (!want || want === '?') return personaKey ? `🎭 現在: ${personaKey}（自発おしゃべりON）` : '🎭 現在: 通常（自発おしゃべりOFF）';
        if (['off', 'normal', 'plain', 'なし', '通常', 'オフ'].includes(want)) return setPersona('');
        const key = PERSONA_ALIAS[want] || (PERSONAS[want] ? want : null);
        if (!key) return `そのモードは無い（使えるの: ${Object.keys(PERSONAS).join(', ')} / off）`;
        return setPersona(key);
      }
      case 'zunda':  // トグル
        return setPersona(personaKey === 'zundamon' ? '' : 'zundamon');
      case 'ears': {  // 通話音声の聞き取りトグル
        const want = q.toLowerCase();
        const turnOff = ['off', 'stop', 'なし', 'オフ', '0'].includes(want);
        const turnOn = ['on', 'start', 'オン', '1'].includes(want);
        if (turnOff || (!turnOn && listening)) {
          await agora.stopListen(page); listening = false; return '🙉 聞き取りOFF';
        }
        if (!listen.modelReady()) return `whisper モデルが無い: ${listen.modelPath()}`;
        const r = await agora.startListen(page); listening = true;
        return `👂 聞き取りON（接続音声 ${r?.sources ?? 0}）${personaKey ? ` / ${personaKey}で返す` : ''}`;
      }
      case 'voice': {  // 読み上げトグル
        const want = q.toLowerCase();
        const turnOff = ['off', 'stop', 'なし', 'オフ', '0'].includes(want);
        const turnOn = ['on', 'start', 'オン', '1'].includes(want);
        if (turnOff || (!turnOn && speaking)) { speaking = false; return '🔇 読み上げOFF'; }
        await tts.voicevoxAlive(); speaking = true;
        return `🗣 読み上げON（${tts.engineName()}）`;
      }
      default: return null;
    }
  } catch (e) { return `エラー: ${e.message}`; }
}

async function main() {
  // 通話待ち受け: Emo が通話に入る（active で拾える）まで polling し、見つけたら自動 join。
  //   get_active_call_post(SELF_UID) を叩くので polling は控えめ（既定15秒）に。
  const WAIT_MS = Number(process.env.YAY_WAIT_MS || 15000);
  console.log('[bot] 通話待ち受け開始（Emoが通話に入ったら自動参加）…');
  for (;;) {
    creds = await fetchCreds().catch((e) => ({ ok: false, error: e.message }));
    if (creds && creds.ok) break;
    const reason = creds?.error || '不明';
    if (!/参加中の通話が無い/.test(String(reason))) console.log('[bot] creds 取得待ち:', reason);
    await sleep(WAIT_MS);
  }
  console.log('[bot] ✓ 通話発見→自動参加 channel=%s uid=%s rtm=%s', creds.channel, creds.uid, creds.rtm_token ? 'yes' : 'no');

  const fs = await agora.startFileServer(0);
  fileBase = `http://127.0.0.1:${fs.port}`;
  console.log('[bot] file server', fileBase);

  const a = await agora.launchAgora({ headless: !process.env.HEADFUL });
  page = a.page;
  // RTC/RTM とも Agora アカウント = conference_call_user_uuid（文字列）。
  //   トークンの crc_uid が uuid の CRC32 に一致（2026-06-03 実走で確認）。
  const joined = await agora.join(page, {
    appId: creds.app_id, channel: creds.channel,
    rtcToken: creds.rtc_token, uid: creds.conference_call_user_uuid,
    rtmToken: creds.rtm_token, rtmUid: creds.conference_call_user_uuid,
  });
  console.log('[bot] join:', JSON.stringify(joined));
  if (!joined.rtc?.ok) console.error('[bot] ⚠ RTC参加失敗（音楽流せない）:', joined.rtc?.error);
  if (!joined.rtm?.ok) console.error('[bot] ⚠ RTM参加失敗（チャット読/送不可）:', joined.rtm?.error, '→ RTMチャンネル名/形式の発見が必要');

  // ★自己判定は RTM 発言者ID = conference_call_user_uuid（Yay uid ではない）。
  //   これを誤ると bot が自分の発言に返信して無限ループする（2026-06-03 修正）。
  const SELF_RTM = String(creds.conference_call_user_uuid || SELF_UID);
  console.log('[bot] self RTM id =', SELF_RTM);

  // 初期音量（既定15、YAY_MUSIC_VOL で上書き可）
  if (process.env.YAY_MUSIC_VOL) { const r = await agora.setMusicVolume(page, process.env.YAY_MUSIC_VOL); console.log('[bot] 初期音量', r?.vol); }

  // join 直後の inbox を一掃（参加前の残/エコーに反応しない）
  try { await agora.drainInbox(page); } catch {}

  const stateExisted = existsSync(CONFIG.stateFile);
  const seen = new Set(loadState().seen);
  console.log('[bot] 稼働開始', stateExisted ? '(seen継承)' : '(初回)');
  console.log('[bot] 人格:', personaKey || '通常', personaSys ? `/ 自発おしゃべり ${IDLE_MIN_MS / 1000}〜${IDLE_MAX_MS / 1000}s` : '/ 自発OFF', '（チャットで /zunda 切替）');

  // 自発おしゃべり用の状態
  const recentLines = [];       // ローリング会話履歴（古→新）
  const pushLine = (s) => { recentLines.push(s); if (recentLines.length > 14) recentLines.shift(); };
  // 人格ONで起動した場合は直後に一発目を出す（以降は中スパン）。OFFなら通常待機。
  lastActivityAt = personaSys ? Date.now() - IDLE_QUIET_MS - 1 : Date.now();
  nextIdleAt = Date.now();

  // テスト再生: YAY_TEST_PLAY="曲名" で起動時に1曲だけ流す（RTC publish 経路の実機確認用）。
  if (process.env.YAY_TEST_PLAY && joined.rtc?.ok) {
    console.log('[bot] ▶ TEST_PLAY:', process.env.YAY_TEST_PLAY);
    const r = await handleCommand('/play ' + process.env.YAY_TEST_PLAY);
    console.log('[bot] TEST_PLAY 結果:', r);
  }

  // 自動ライブ取り込み: YAY_AUTO_LIVE="BlackHole" 等で join 直後にシステム音声入力を掴んで配信開始。
  //   Spotify DJ 運用（Spotify→複数出力装置→BlackHole→ここで取り込み）で究が /lv を打たずに済む。
  if (process.env.YAY_AUTO_LIVE && joined.rtc?.ok) {
    const m = String(process.env.YAY_AUTO_LIVE);
    console.log('[bot] ▶ AUTO_LIVE:', m);
    const r = await handleCommand('/lv ' + m);
    console.log('[bot] AUTO_LIVE 結果:', r);
  }

  // 自動聞き取り: YAY_LISTEN=1 で join 直後に通話音声の文字起こし→返信を有効化。
  if (process.env.YAY_LISTEN && joined.rtc?.ok) {
    if (listen.modelReady()) {
      const r = await agora.startListen(page); listening = true;
      console.log('[bot] 👂 AUTO_LISTEN ON sources=', r?.sources, 'model=', listen.modelPath());
    } else console.error('[bot] ⚠ YAY_LISTEN 指定だが whisper モデル無し:', listen.modelPath());
  }

  // 自動読み上げ: YAY_TTS=1 で返信のTTSを有効化。
  if (process.env.YAY_TTS) {
    await tts.voicevoxAlive(); speaking = true;
    console.log('[bot] 🗣 AUTO_TTS ON engine=', tts.engineName());
  }

  for (;;) {
    // キュー自動送り: 再生が止まっててキューがあれば次を流す
    if (!starting) {
      try {
        const st = await agora.status(page);
        if (!st?.nowPlaying) {
          if (queue.length) {
            const r = await startTrack(queue.shift());   // タイトル通知は startTrack 内で実施済み
            console.log('  ▶ next:', r);
          } else if (nowQuery && nowQuery !== 'live') { nowQuery = null; }
        }
      } catch {}
    }

    // 通話音声の聞き取り: 切り出された発話を whisper で文字起こし → EmoCC（人格反映）で返信
    if (listening) {
      let utts = [];
      try { utts = await agora.drainUtterances(page); } catch (e) { console.error('drainUtt', e.message); }
      for (const u of utts) {
        let heard = '';
        try { heard = await listen.transcribe(u.b64, u.rate); } catch (e) { console.error('whisper', e.message); }
        if (!heard) continue;
        console.log(`  👂 聞: ${heard}`);
        pushLine(`声: ${heard}`);
        lastActivityAt = Date.now();
        if (canReply()) {
          const context = recentLines.slice(-10).join('\n');
          try {
            const reply = (await emoccReply(context, { system: personaSys })).replace(/^[!\/]\S*\s*/, '').trim();
            if (reply) { await sendYayChat(page, reply); markReplied(); pushLine(`自分: ${reply}`); console.log('  → 声返信:', reply); await sayOut(reply); }
          } catch (e) { console.error('voice reply err', e.message); }
        }
      }
    }

    // 自発おしゃべり（人格指定時のみ）: 場が静かなら中スパンで自分から一言
    if (personaSys && IDLE_MAX_MS > 0 && Date.now() >= nextIdleAt
        && (Date.now() - lastActivityAt) > IDLE_QUIET_MS && canReply()) {
      try {
        const ctx = recentLines.slice(-10).join('\n');
        const line = (await idleChatter(ctx, { system: personaSys })).replace(/^[!\/]\S*\s*/, '').trim();
        if (line) {
          await sendYayChat(page, line); markReplied();
          pushLine(`自分: ${line}`);
          lastActivityAt = Date.now();
          console.log('  💬 idle:', line);
          await sayOut(line);
        }
      } catch (e) { console.error('idle err', e.message); }
      nextIdleAt = Date.now() + idleSpan();
    }

    let raw = [];
    try { raw = await agora.drainInbox(page); } catch (e) { console.error('drain err', e.message); }
    const msgs = raw.map(parseMsg).filter((m) => m.text);
    const fresh = msgs.filter((m) => !seen.has(m.id) && m.author !== SELF_RTM);
    fresh.forEach((m) => seen.add(m.id));

    if (fresh.length) {
      lastActivityAt = Date.now();
      const ts = new Date().toLocaleTimeString('ja-JP');
      fresh.forEach((m) => { console.log(`[${ts}] 新着 ${m.author}: ${m.text}`); pushLine(`${m.author}: ${m.text}`); });
      for (const m of fresh) {
        const mr = await handleCommand(m.text);
        if (mr && canReply()) { await sendYayChat(page, mr).catch((e) => console.error('send', e.message)); markReplied(); console.log('  ♪', mr); }
      }
      const conv = fresh.filter((m) => !/^[!\/]/.test(m.text));
      if (conv.length && canReply()) {
        const context = recentLines.slice(-10).join('\n');
        try {
          let reply = (await emoccReply(context, { system: personaSys })).replace(/^[!\/]\S*\s*/, '').trim();
          if (reply) { await sendYayChat(page, reply); markReplied(); pushLine(`自分: ${reply}`); lastActivityAt = Date.now(); console.log('  → 返信:', reply); await sayOut(reply); }
          else console.log('  → [skip]');
        } catch (e) { console.error('reply err', e.message); }
      } else if (conv.length) console.log('  → 連投ガードで保留');
      saveState({ seen: [...seen].slice(-2000) });
    }
    await sleep(CONFIG.pollMs);
  }
}

process.on('unhandledRejection', (e) => console.error('unhandledRejection:', e?.message || e));
(async () => {
  for (;;) {
    try { await main(); } catch (e) { console.error('[bot] 落ちた→5秒後再起動:', e.message); await sleep(5000); }
  }
})();
