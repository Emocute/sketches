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
import { readFileSync, writeFileSync, existsSync, appendFileSync, mkdirSync, statSync, readdirSync } from 'node:fs';
import { execFile, execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { CONFIG } from './config.mjs';
import { emoccReply, idleChatter, PERSONAS } from './lib/claude.mjs';
import * as agora from './lib/agora.mjs';
import * as music from './lib/music_agora.mjs';
import * as spotify from './lib/music.mjs';   // 旧Spotify/BlackHole経路を再利用（/sp 自動操作）
import * as listen from './lib/listen.mjs';
import * as tts from './lib/tts.mjs';

const PY = fileURLToPath(new URL('./.venv/bin/python', import.meta.url));
const API = fileURLToPath(new URL('./yay_api.py', import.meta.url));
const SELF_UID = String(process.env.YAY_SELF_UID || '11320230');
// なりきり人格（YAY_PERSONA=zundamon 等が初期値）。チャットから /mode で実行時切替できる。
//   ※ 人格(語尾/声色) と 自発おしゃべり(idleChatOn) は独立トグル（究指示 2026-06-06: 分離）。
let personaKey = String(process.env.YAY_PERSONA || '').toLowerCase();
let personaSys = PERSONAS[personaKey] || undefined;
// 自発おしゃべり（場が静かな時に自分から一言）。人格とは無関係に ON/OFF できる。
let idleChatOn = /^(1|on|true|yes)$/i.test(String(process.env.YAY_IDLE_ON || ''));
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
// フラグだけ即時永続（seen を壊さずマージ書き込み。トグル直後の確実な保存用）。
const persistFlags = () => {
  try { const s = loadState(); s.ownerYayId = ownerYayId; s.cmdsEnabled = cmdsEnabled; saveState(s); }
  catch (e) { console.error('persistFlags', e.message); }
};

// yay_api.py を叩いて creds JSON を得る（最終行が JSON）。
//   発見uid = YAY_WATCH_UID(究本人のuid) があればそれ、無ければ SELF_UID。
//   別アカ運用時は WATCH_UID に究の通話を見張らせ、EmoCC(SELF) として join＝衝突せず共存。
const DISCOVER_UID = String(process.env.YAY_WATCH_UID || CONFIG.watchYayId || SELF_UID);
// 監視運用か（究=えものアカウントを見張って枠に自動入室）。SELF と違う＝別アカ監視モード。
const WATCHING = String(DISCOVER_UID) !== String(SELF_UID);
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
  // ★送信者の Yay user id を抽出: Yay は msg の id を "<yayUserId>_<ts>" 形式で振る
  //   （2026-06-07 実走確認: 究=9714060_..., bot=11320230_...）。publisher(uuid) は通話ごとに
  //   変わるが、この yayUserId は安定＝名簿(id→nickname)と結合して名前で認識できる。
  let userId = null;
  if (msgId) { const um = /^(\d+)_/.exec(String(msgId)); if (um) userId = um[1]; }
  return { id: msgId ? `id:${msgId}` : `${author}|${m.ts}|${text}`, author, userId, text, type };
}

// Yayが表示できる送信エンベロープ。受信と同形式: `chat {"text","created_at_seconds","id"}`。
function yayEnvelope(text) {
  const now = Date.now();
  const payload = { text: String(text), created_at_seconds: Math.floor(now / 1000), id: `${SELF_UID}_${now}` };
  return 'chat ' + JSON.stringify(payload);
}
const sendYayChat = (p, text) => agora.sendChat(p, yayEnvelope(text));

let page, fileBase, creds, browser, fileServer;

// ===== コマンド体系（汎用・1〜2文字エイリアス対応）=====
const PLAYLIST_LIMIT = 100;   // YouTube プレイリスト展開の上限曲数（チャット氾濫・過負荷防止）
let queue = [];        // 未再生キュー（query文字列）
let queueRepeat = false; // キュー全体リピート（曲が終わるたび末尾へ戻して循環。/l の一曲ループとは別）
let nowQuery = null;   // 再生中の曲名/ラベル
let nowIsSpotify = false; // 現在の再生が Spotify(live BlackHole)経路か（skip/stop/自動送りの判定用）
let spEndedPolls = 0;  // Spotify 再生終了の連続検知カウンタ（自動送りの誤検知防止）
let starting = false;  // 多重起動ガード

// 話者ガード: このオーナーの発言だけツール全開（ファイル/Bash）。他人は会話のみ。
//   /iam <合言葉> で本人が登録（合言葉は通話の他人のなりすまし防止）。state.json に永続。
//   ★判定は安定した Yay user id（uuid は通話ごとに変わり跨ぐと壊れるため。2026-06-07）。
let ownerYayId = null;
const OWNER_SECRET = process.env.YAY_OWNER_SECRET || 'kiwamu';

// canonical → [aliases]（先頭が正式名）。`/` でも `!` でも発火。
const CMD = {
  help:   ['help', 'h'],
  helpshort: ['?'],
  play:   ['play', 'p', 'sp', 'spotify', 'スポ', 'スポティ'],  // 一本化: 曲名=Spotify優先→YouTube自動切替、URLは種別で振分
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
  clear:  ['clear', 'cls', 'c', 'qc', 'クリア', 'キュークリア', '全消', 'キュー消去'],
  ping:   ['ping', 'pi'],
  leave:  ['leave', 'bye'],
  mode:   ['mode', 'm', 'persona'],
  zunda:  ['zunda', 'ずんだ'],
  idle:   ['idle', 'jihatsu', 'chatter', '自発', 'おしゃべり', '独り言'],  // 自発おしゃべり ON/OFF（人格と独立）
  ttsvol: ['vv', 'koevol', '声量', '声音量'],   // 読み上げ(ずんだもん声)の音量 0-100
  duck:   ['duck', 'ダッキング', '音楽残し'],    // TTS中の音楽残し率 0-100（大=音楽を下げない）
  voicemode: ['voicemode', 'vm', '声モード', 'こえモード', '声色'],   // 声モード normal/auto/power/sad
  ears:   ['ears', 'listen', '耳', '聞く', 'kiku'],
  voice:  ['voice', 'yomi', 'tts', '読み', '読み上げ', '喋る', 'koe'],
  status: ['status', 'st', '状態', 'state'],
  qlist:  ['ql', 'qlist', 'きゅー', 'リスト'],
  qdel:   ['qd', 'qdel', 'rm', '消'],
  qup:    ['qu', 'qup', 'up', '上'],
  qdn:    ['qj', 'qdn', 'down', '下'],
  qrepeat:['qr', 'repeat', 'rp', 'リピート', '繰り返し'],   // キュー全体リピート on/off（/l は一曲ループ）
  qshuffle:['qsh', 'shuffle', 'shuf', 'sh', 'シャッフル', 'ランダム'],  // キューをランダム並べ替え
  iam:    ['iam', 'owner', 'オーナー', '俺'],   // 本人登録（/iam <合言葉>）
  whoami: ['whoami', 'myid', '誰'],             // 自分のRTM IDを表示
  volup:  ['volup', 'vu', '音量上げ'],
  voldown:['voldown', 'vd', '音量下げ'],
  rec:    ['rec', 'record', '録音'],            // 録音 状態/保存/停止/開始
  jingle: ['jingle', 'aisatsu', '挨拶', 'あいさつ', 'いらっしゃい'],  // 入退室あいさつ on/off
  cmds:   ['cmds', 'commands', 'cmd', 'コマンド'],   // 操作コマンド受付 on/off（オーナーのみ。OFFでも /cmds は効く）
};
const ALIAS = {}; for (const [k, vs] of Object.entries(CMD)) for (const v of vs) ALIAS[v] = k;
// トグル状態
let listening = false;  // 聞き取り（通話音声→文字起こし→返信）
let speaking = false;   // 読み上げ（返信のTTS＝ずんだもん声）
let cmdsEnabled = true; // /コマンド受付（OFFで /play 等の操作コマンドを全無視。会話・音楽再生・ジングルは継続。切替はオーナーのみ /cmds）

const onoff = (b) => (b ? '🟢ON' : '⚪OFF');
// いまの状態ブロック（/st と /h の冒頭で共用）
function statusBlock() {
  return [
    `🗣 読み上げ: ${onoff(speaking)}（声モード:${voiceMode} / 音量${lastTtsVol} / 音楽残し${lastDuck}%）`,
    `👂 聞き取り: ${onoff(listening)}`,
    `🎭 ずんだもん語尾: ${onoff(personaKey === 'zundamon')}`,
    `💬 自発おしゃべり: ${onoff(idleChatOn)}`,
    `🎉 入退室あいさつ: ${onoff(jingleOn)}`,
    `🎛 コマンド受付: ${onoff(cmdsEnabled)}`,
    nowQuery ? `🎵 再生中: ${nowQuery}` : '🎵 再生: なし',
    `📜 キュー: ${queue.length}曲 / リピート: ${onoff(queueRepeat)}`,
  ].join('\n');
}
function renderHelpFull() {
  return [
    '🎧 EmoCC コマンド（詳細）',
    '― いまの状態 ―',
    statusBlock(),
    '― 切替（各コマンドでトグル / on・off 明示も可）―',
    '/voice（読）= 読み上げ。返信を自動でずんだもん声で喋る',
    '/vv 0-100 = 読み上げ(ずんだもん声)の音量（既定30）',
    '/duck 0-100 = 声の時の音楽残し率（既定70。大=音楽を下げない）',
    '/voicemode <normal/auto/power/sad> = 声モード（既定normal=元気な普通のずんだもん）',
    '/ears（聞）= 聞き取り。通話の音声を文字起こし→自動返信',
    '/mode <モード> = 人格切替（zundamon/off 等）',
    '  ・/zunda = ずんだもん語尾 on/off（声・語尾のみ）',
    '/idle = 自発おしゃべり on/off（人格と独立。静かな時に自分から一言）',
    '/jingle = 入退室あいさつ on/off（入ってきた人に名前で「いらっしゃい」）',
    '/cmds = 操作コマンド受付 on/off（オーナー専用。OFFで /play 等を無視・会話と音楽は継続。/cmds off｜on｜?）',
    '― 音楽再生 ―',
    '/p <曲/URL> = 再生開始（曲名は Spotify 優先→無ければ YouTube、URL は自動判別）',
    '/q <曲> = キューに追加（再生中なら末尾へ）。複数曲は「/q 曲A, 曲B, 曲C」or 改行で一括投入',
    `  ・YouTube プレイリストURL を渡すと全曲をキューに展開（最大${PLAYLIST_LIMIT}曲）`,
    '/s（次）= スキップ / /x（停止）= 全停止',
    '/ps = 一時停止 / /r = 再開',
    '/v 0-100 = 音量設定（既定15）',
    '/np = 再生中の曲 / /l = 一曲ループ',
    '/lv [match] = システム音声配信（例: /lv mic）',
    '/c = キュー消去',
    '― キュー操作 ―',
    '/q / /qlist = キュー一覧（番号付き）',
    '/qd <N> = N番削除 / /qu <N> = N番を前へ / /qj <N> = N番を後ろへ',
    '/rp = キューリピート on/off（最後まで流したら頭から繰り返す）',
    '/sh = キューシャッフル（ランダム並べ替え）',
    '― その他 ―',
    '/d = 音声入力デバイス一覧',
    '/st = 状態確認 / /h = 詳細ヘルプ / /? = 簡易ヘルプ',
    '/pi = ping / /bye = 通話から退出',
  ].join('\n');
}

function renderHelpShort() {
  return [
    '🎧 EmoCC コマンド（簡易）',
    '/voice /vv <n> /ears /mode <m> /zunda /idle /jingle … 機能 on/off',
    '/p <曲> /s /x /ps /r /v <n> /l /np … 再生制御',
    '/q（一覧）/q <曲>（追加）/qd /qu /qj /rp(リピート) /sh(シャッフル) /c … キュー',
    '/lv /d /st /pi /bye … その他',
    '複数曲=「/q 曲A, 曲B」/ YTプレイリストURLは全曲展開 / 1msgに複数コマンド可（改行）',
    '詳細: /h',
  ].join('\n');
}

function renderHelp() {
  return renderHelpFull();
}
// 声モード（究指示 2026-06-07）: 既定は normal＝元気な普通のずんだもん固定。/voicemode で切替。
//   normal=ノーマル固定 / auto=状況で自動 / power=パワフル固定 / sad=悲しい固定。
let voiceMode = String(process.env.YAY_VOICE_MODE || CONFIG.voiceMode || 'normal').toLowerCase();

// auto モード時に文章の感情でずんだもん声色を選ぶ（sad→power→normal の順で判定）。
function pickZundaVoice(text) {
  const t = String(text || '');
  if (/(ごめん|すまん|申し訳|残念|悲し|つら|辛|寂し|さみし|しんど|大丈夫\?|無理しない|心配|可哀|かわいそう|……|。。。)/.test(t)) return 'zundamon_sad';
  if (/(やった|すごい|最高|いくぞ|いこう|がんば|ファイト|うれし|嬉し|わーい|やっほ|テンション|ずんだパワー|！！|!!|🎉)/.test(t)) return 'zundamon_power';
  if ((t.match(/[!！]/g) || []).length >= 2) return 'zundamon_power';
  return 'zundamon';
}
// 実際に使う声色をモードで決める。normal が既定（元気な普通のずんだもん固定）。
function chooseVoice(text) {
  if (voiceMode === 'power') return 'zundamon_power';
  if (voiceMode === 'sad') return 'zundamon_sad';
  if (voiceMode === 'auto') return pickZundaVoice(text);
  return 'zundamon';   // normal（既定）
}

// 返信を喋る（speaking時のみ）。TTS で WAV 生成 → Agora RTC に publish。
// 声は常にずんだもん（声色 normal/power/sad は文章の感情で自動選択）。
async function sayOut(text) {
  if (!speaking) return;
  try {
    const voiceKey = chooseVoice(text);   // 声モードに従って声色を決める（既定=元気な普通）
    console.log('[sayOut] voiceKey=', voiceKey, 'mode=', voiceMode);
    const r = await tts.speak(text, { voice: voiceKey });
    console.log('[sayOut] tts.speak result:', { ok: r.ok, engine: r.engine, file: r.file?.slice(-30) });
    if (!r.ok || !r.file) { console.error('[sayOut] ERR: no file', r); return; }
    // WAV ファイルを Agora playTTS で再生（音楽トラックは止めず ttsGain に乗せ、再生中はダッキング）
    const url = agora.fileUrl(fileBase, r.file);
    console.log('[sayOut] playTTS call:', url.slice(-50));
    const playResult = await agora.playTTS(page, url).catch((e) => { console.error('[sayOut] playTTS ERR:', e.message); return null; });
    console.log('[sayOut] playTTS result:', playResult);
  } catch (e) {
    console.error('[sayOut] ERR exception:', e.message, e.stack?.split('\n')[1]);
  }
}

// 人格の実行時切替（再起動不要）。語尾/声色のみ。自発おしゃべりとは独立（/idle で別管理）。
function setPersona(key) {
  personaKey = key || '';
  personaSys = personaKey ? PERSONAS[personaKey] : undefined;
  return personaSys ? `🎭 ${personaKey} モードON（語尾/口調）。自発おしゃべりは別（/idle）` : '🎭 通常モードに戻した（語尾オフ）';
}

// 自発おしゃべりの ON/OFF（人格とは独立）。ONにしたら直後に一発目を出す。
function setIdleChat(on) {
  idleChatOn = !!on;
  if (idleChatOn) { lastActivityAt = Date.now() - IDLE_QUIET_MS - 1; nextIdleAt = Date.now(); return `💬 自発おしゃべりON（${IDLE_MIN_MS / 1000}〜${IDLE_MAX_MS / 1000}s おきに静かなら一言）`; }
  return '💬 自発おしゃべりOFF';
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
    nowIsSpotify = false;
    return { ok: true, title };
  } finally { starting = false; }
}
const notFoundMsg = (q) => `❌ 見つかりませんでした: ${q}`;

// ── Spotify 自動操作（Playwright で Spotify Web 検索→再生 → BlackHole → RTC publish）──
let musicReady = false;          // music ブラウザ(9223) に connectMusic 済みか
let lastVol = Number(process.env.YAY_MUSIC_VOL || 2);  // 直近音量（相対調整用）。既定2（2026-06-07 究指示 15→2）
let lastTtsVol = Number(process.env.YAY_TTS_VOL || 30);  // 直近の読み上げ音量（/vv 表示用）
let lastDuck = Number(process.env.YAY_DUCK || 70);  // TTS中の音楽残し率%（既定70。/duck で調整）

async function ensureMusicBrowser() {
  const up = async () => { try { const r = await fetch('http://127.0.0.1:9223/json/version'); return r.ok; } catch { return false; } };
  if (await up()) return true;
  // 9223 が無ければ launcher を起動して待つ
  try { execFile('zsh', [fileURLToPath(new URL('./scripts/launch_music.sh', import.meta.url))], { cwd: fileURLToPath(new URL('.', import.meta.url)) }); } catch (e) { console.error('launch_music', e.message); }
  for (let i = 0; i < 24; i++) { if (await up()) return true; await sleep(500); }
  return false;
}

async function startSpotify(query) {
  if (!CONFIG.spotifyEnabled) return { ok: false, reason: 'Spotify 無効（config.spotifyEnabled=false）' };
  if (!(await ensureMusicBrowser())) return { ok: false, reason: '音楽ブラウザ(9223)が起動できない' };
  try {
    if (!musicReady) { await spotify.connectMusic(); musicReady = true; }
    await sendYayChat(page, `🎧 Spotify: ${query}`).catch(() => {});  // 再生前に通知（全呼び出し共通）
    const r = await spotify.playSpotify(query);   // 検索/URL→再生→BlackHole へ setSinkId（検証付き）
    if (!r.route?.ok) return { ok: false, reason: r.route?.reason || 'BlackHole 経路NG', drm: true };
    await agora.playLive(page, 'BlackHole');       // BlackHole 入力を RTC に publish
    nowQuery = 'Spotify: ' + query;
    nowIsSpotify = true;
    return { ok: true };
  } catch (e) { musicReady = false; return { ok: false, reason: e.message }; }
}

// URL 判定
const isHttpUrl = (s) => /^https?:\/\//i.test(String(s).trim());
const isSpotifyRef = (s) => { const t = String(s).trim(); return /open\.spotify\.com/i.test(t) || /^spotify:/i.test(t); };

// 統合再生エンジン（/play 一本化）。曲名=Spotify優先→YouTube自動切替、URLは種別で振分。
//   Spotify URL → Spotify Web Player で直接 / 他URL → yt-dlp / 曲名 → Spotify→(失敗時)YouTube。
//   CONFIG.spotifyEnabled=false 時: Spotify URL はエラー、曲名は直接 YouTube へ。
async function startAny(query) {
  const q = String(query).trim();
  if (!q) return { ok: false, notfound: true, query: q };
  if (isSpotifyRef(q)) {
    if (!CONFIG.spotifyEnabled) return { ok: false, notfound: true, query: q, reason: 'Spotify 無効（YouTube では Spotify URL は再生不可）' };
    const r = await startSpotify(q);
    return r.ok ? { ok: true, src: 'spotify' } : { ok: false, notfound: true, query: q, reason: r.reason };
  }
  if (isHttpUrl(q)) {   // YouTube 等の動画/音声 URL は yt-dlp 経路
    const r = await startTrack(q);
    return r.ok ? { ok: true, src: 'yt' } : { ok: false, notfound: true, query: q };
  }
  // ただの曲名: Spotify が有効なら Spotify 優先 → ダメなら YouTube。無効なら直接 YouTube。
  if (CONFIG.spotifyEnabled) {
    const sp = await startSpotify(q);
    if (sp.ok) return { ok: true, src: 'spotify' };
    console.log('  Spotify不可→YouTube fallback:', sp.reason);
  }
  const yt = await startTrack(q);
  return yt.ok ? { ok: true, src: 'yt' } : { ok: false, notfound: true, query: q };
}

// ファイル/コード/開発系の意図か（true の時だけ重い tools 全開パスへ昇格）。
//   ヒットしなければ高速な会話パス（cwd=tmp・CLAUDE.md 読込無し）で返す。
function wantsTools(text) {
  return /ファイル|フォルダ|ディレクトリ|repo|リポ|コード|code|スクリプト|直して|修正|実装|追加して|書いて|バグ|エラー|例外|ログ|grep|検索して|調べて|開いて|見て|確認して|読んで|テスト|ビルド|デプロイ|push|commit|git|どうなって|中身|\.(mjs|jsx?|tsx?|py|json|md|html|css|vue|sh|toml|ya?ml)\b/i.test(String(text));
}

// 自然言語 → スラッシュコマンド（オーナー本人の発言だけに適用）。制御意図でなければ null。
function nlToCommand(text) {
  const t = String(text).trim();
  let m;
  if (/録音.*(止め|停止|終わ|やめ|オフ)/.test(t)) return '/rec stop';
  if (/(ここまで|今まで).*(保存|録音)|録音.*保存/.test(t)) return '/rec save';
  if (/録音(して|開始|始め|オン|を?しといて)?$/.test(t) || /録音.*(して|開始|始め|オン)/.test(t)) return '/rec on';
  if ((m = t.match(/(?:音量|ボリューム|ボリュ)\D*?(\d{1,3})/))) return `/vol ${m[1]}`;
  if (/(?:音量|ボリューム|音)/.test(t) && /(上げ|大きく|でかく|あげて|うるさ)/.test(t)) return '/volup';
  if (/(?:音量|ボリューム|音)/.test(t) && /(下げ|小さく|さげて|ちいさ|静か|絞)/.test(t)) return '/voldown';
  if (/(一時停止|ポーズ|ちょっと止め)/.test(t)) return '/pause';   // stop より先（「一時停止」に「停止」が含まれるため）
  if (/(再開|続きから|戻して再生)/.test(t)) return '/resume';
  if (/(止めて|停めて|ストップ|止めろ|停止|音楽.*消)/.test(t)) return '/stop';   // 「やめて」は会話で誤爆するため除外
  if (/(次の?曲|次に?して|次いって|スキップ|とばして|飛ばして|チェンジして)/.test(t)) return '/skip';
  const pv = t.match(/(かけて|流して|再生して|プレイして|聴きたい|聞きたい|かけろ|流せ|プレイ|かけ)/);
  if (pv) {
    // /play 一本化: Spotify/YouTube の振り分けは startAny が自動でやるので語句から外すだけ
    let q = t.slice(0, pv.index).replace(/spotify|スポティファイ|スポ(?!ーツ)/ig, '').trim();
    q = q.replace(/^(で|の|を)\s*/, '').replace(/(を|の曲|って)\s*$/, '').trim();
    if (!q) return null;
    return `/play ${q}`;
  }
  return null;
}

// ── 録音（通話まるごと → webm 逐次追記 → 停止/離脱で mp3 128kbps 変換）──
//   究指示「常に録音して記録」: join 直後に自動開始、毎ループでチャンクをファイルへ追記。
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

async function drainRecToFile() {
  if (!recState?.active) return;
  try {
    const chunks = await agora.drainRecChunks(page);
    for (const b64 of chunks) { try { appendFileSync(recState.webmPath, Buffer.from(b64, 'base64')); } catch (e) { console.error('[rec] append', e.message); } }
  } catch (e) { console.error('[rec] drain', e.message); }
}

// webm → mp3 128kbps（ffmpeg）。途中スナップショット(keepGoing=true)でも停止確定でも使える。
function convertToMp3(webmPath, mp3Path) {
  try {
    execFileSync('ffmpeg', ['-y', '-i', webmPath, '-c:a', 'libmp3lame', '-b:a', '128k', mp3Path], { stdio: 'ignore' });
    const kb = Math.round(statSync(mp3Path).size / 1024);
    return { ok: true, kb };
  } catch (e) { return { ok: false, reason: e.message }; }
}

// webm → mp3 非ブロッキング版（起動時スイープ用。execFileSync だと大ファイルで event loop が固まる）。
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
//   join のたびに走らせる＝前回クラッシュ/kill で mp3 化されなかった分を確実に救う（冪等）。
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

// 録音停止＋mp3化（/leave・bot停止・/rec stop で呼ぶ）。
async function stopCallRecording() {
  if (!recState?.active) return null;
  recState.active = false;
  try {
    const r = await agora.stopRecord(page);
    for (const b64 of (r?.chunks || [])) { try { appendFileSync(recState.webmPath, Buffer.from(b64, 'base64')); } catch {} }
  } catch (e) { console.error('[rec] stop', e.message); }
  const mins = Math.round((Date.now() - recState.startedAt) / 60000);
  const conv = convertToMp3(recState.webmPath, recState.mp3Path);
  const out = { ...recState, mins, conv };
  console.log('[rec] ■ 停止→mp3', conv.ok ? `${recState.mp3Path} (${conv.kb}KB)` : 'ffmpeg失敗:' + conv.reason);
  recState = null;
  return out;
}

// ── 入退室ジングル（参加者名簿の差分 → 挨拶。チャット＋ずんだもん声）──
//   設計: Agora の uid(conference_call_user_uuid) は不透明で名前に紐付かない。
//   そこで yay_api.py members で通話の participant 一覧(Yay user=id/nickname)を周期取得し、
//   差分で join/leave を検出して名前付きで挨拶する。声は既存 playTTS（音楽を自動ダッキング）。
const JC = () => CONFIG.jingle || {};
let jingleOn = JC().enabled !== false;
const roster = new Map();   // Yay userId(str) → { nick, lastSeen, present }
// publisher(uuid・通話ごとに変わる) → Yay userId（chat の id 接頭辞から学習）。声の話者名解決にも使う。
const uuidToYayId = new Map();
const yayIdToNick = (id) => (id != null ? roster.get(String(id))?.nick : null) || null;
// チャット発言者の表示名: Yay id→nick を最優先、無ければ uuid 学習経由、最後は短縮 uuid。
function speakerName(m) {
  const yid = m.userId || uuidToYayId.get(m.author) || null;
  return yayIdToNick(yid) || (yid ? `user${yid}` : (m.author ? String(m.author).slice(0, 6) : '誰か'));
}
// 声の発話の話者名: utterance.uid(=publisher uuid) → 学習済み yayId → nick。未学習なら「誰か」。
function speakerNameByUuid(uuid) {
  return yayIdToNick(uuidToYayId.get(String(uuid))) || '誰か';
}
// 今この通話に居る人の名前一覧（在室かつ nick 既知）。返信文脈のヘッダに使う。
function presentNames() {
  return [...roster.values()].filter((r) => r.present && r.nick).map((r) => r.nick);
}
let memberSeeded = false;   // 初回ポーリングは無言でシード（既存メンバーに連打しない）
let lastMemberPollAt = 0;
let lastJingleAt = 0;
let jingleQueue = [];        // {kind:'join'|'leave', nick, returning}

// 名簿取得（python 1回 spawn、最終行 JSON）
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
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
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
// ジングルの声（返信TTS の speaking トグルとは独立。voice/quietHours で制御）
async function sayJingle(text) {
  if (JC().voice === false || inQuietHours()) return;
  try {
    const r = await tts.speak(text, { voice: chooseVoice(text) });
    if (!r.ok || !r.file) return;
    await agora.playTTS(page, agora.fileUrl(fileBase, r.file)).catch((e) => console.error('[jingle] playTTS', e.message));
  } catch (e) { console.error('[jingle] say', e.message); }
}
// 名簿ポーリング＋差分（throttle はここで持つ。loop から毎周回呼んでよい）
async function pollMembersAndDiff() {
  if (!jingleOn) return;
  const callId = process.env.YAY_CALL_ID || creds?.conference_id || creds?.channel;
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
    if (!id || id === selfId) continue;     // 自分(Emo)は除外
    seenNow.add(id);
    const prev = roster.get(id);
    const nick = u.nickname || prev?.nick || null;
    if (!prev || !prev.present) {
      if (memberSeeded) {
        const gap = prev ? (now - (prev.lastSeen || 0)) : Infinity;
        const flap = prev && gap < 5000;                 // 5秒以内の瞬断=回線フラップ→無音
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
// キュー消化（rate limit。1周回1件）
async function drainJingle() {
  if (!jingleOn || !jingleQueue.length) return;
  const now = Date.now();
  if (now - lastJingleAt < (JC().minGapMs || 8000)) return;
  const j = jingleQueue.shift();
  lastJingleAt = now;
  const line = jingleLine(j);
  const emoji = j.kind === 'leave' ? '👋' : '🎉';
  try { await sendYayChat(page, `${emoji} ${line}`); } catch (e) { console.error('[jingle] chat', e.message); }
  await sayJingle(line);
  console.log(`  ${emoji} jingle:`, line);
}

// YouTube プレイリストURL 判定（list= を持つ youtube/youtu.be リンク）
function isPlaylistUrl(u) {
  return /^https?:\/\//i.test(u) && /(youtube\.com|youtu\.be)/i.test(u) && /[?&]list=/i.test(u);
}
// キュー表示用ラベル（長いURLは短縮、曲名はそのまま）
function qLabel(s) {
  if (!/^https?:\/\//i.test(s)) return s;
  const m = s.match(/[?&]v=([\w-]{6,})/) || s.match(/youtu\.be\/([\w-]{6,})/);
  return m ? `▶ ${m[1]}` : s.slice(0, 48);
}
// キューを番号付きで表示（長大キューは先頭 N 件のみ＝チャット氾濫防止）
function renderQueue() {
  const head = nowQuery ? `🎵 再生中: ${nowQuery}` : '🎵 再生: なし';
  if (!queue.length) return `${head}\n📜 キューは空`;
  const MAX = 15;
  const lines = queue.slice(0, MAX).map((s, i) => `${i + 1}. ${qLabel(s)}`).join('\n');
  const more = queue.length > MAX ? `\n…他${queue.length - MAX}曲` : '';
  return `${head}\n📜 キュー(${queue.length})\n${lines}${more}`;
}
// 番号引数（1始まり）→ 0始まりindex（範囲外は -1）
function qIndex(q) {
  const n = parseInt(q, 10);
  return (Number.isInteger(n) && n >= 1 && n <= queue.length) ? n - 1 : -1;
}

// 1引数を複数曲に分割（カンマ/読点/全角カンマ/改行区切り）。"AC/DC" を割らないため "/" は区切りにしない。
function splitSongs(s) {
  return String(s).split(/\s*[,、，\n]+\s*/).map((x) => x.trim()).filter(Boolean);
}

// 1メッセージ → 複数コマンド行に分割。先頭が ! or / の行＝新コマンド。
// コマンドでない行は直前のコマンドへ ", " で追記（曲名を縦に並べて複数投入できる）。
// 先頭から非コマンド行のみ＝コマンドメッセージではない（空配列＝会話扱い）。
function splitCommandLines(text) {
  const lines = String(text).split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const cmds = [];
  for (const l of lines) {
    if (/^[!\/]/.test(l)) cmds.push(l);
    else if (cmds.length) cmds[cmds.length - 1] += ', ' + l;
  }
  return cmds;
}

// 複数コマンドを順に実行し、応答を連結して返す。
//   null  = コマンドメッセージでなかった（会話/NL パスへ）
//   ''    = コマンドは実行したが表示応答なし（/p 成功等）
async function runCommands(text, author, userId) {
  const cmds = splitCommandLines(text);
  if (!cmds.length) return null;
  const outs = [];
  for (const c of cmds) {
    const r = await handleCommand(c, author, userId);
    if (r) outs.push(r);
  }
  return outs.length ? outs.join('\n―\n') : '';
}

// テキスト → コマンド応答（コマンドでなければ null）
//   author=publisher uuid（通話内一意）、userId=Yay user id（安定。owner 判定に使う）。
async function handleCommand(text, author = '?', userId = null) {
  const mm = String(text).match(/^\s*[!\/]\s*(\S+)\s*([\s\S]*)$/);
  if (!mm) return null;
  const cmd = ALIAS[mm[1].toLowerCase()];
  const q = (mm[2] || '').trim();
  if (!cmd) return null;
  // マスタートグル: 操作コマンド受付の on/off。オーナーのみ。OFF中でもこれだけは常に効く（復帰経路）。
  if (cmd === 'cmds') {
    const isOwnerU = !!ownerYayId && userId && String(userId) === String(ownerYayId);
    if (!isOwnerU) return '🔒 コマンド受付の切替はオーナーだけ（/iam <合言葉> で登録して）';
    const w = q.toLowerCase();
    if (w === '?' || w === 'status') return `🎛 コマンド受付: ${cmdsEnabled ? '🟢ON' : '⚪OFF'}`;
    if (['on', 'start', 'オン', '1', '有効'].includes(w)) cmdsEnabled = true;
    else if (['off', 'stop', 'オフ', '0', '無効', 'なし'].includes(w)) cmdsEnabled = false;
    else cmdsEnabled = !cmdsEnabled;
    persistFlags();
    return cmdsEnabled
      ? '🎛 コマンド受付ON（/play 等の操作コマンドが使える）'
      : '🔇 コマンド受付OFF（/play 等を無視。会話・音楽再生・あいさつは継続。/cmds on で復帰）';
  }
  // OFF中は他の全コマンドを無視（会話返信・音楽再生は別経路でそのまま動く）。
  if (!cmdsEnabled) return null;
  try {
    switch (cmd) {
      case 'help': return renderHelp();
      case 'helpshort': return renderHelpShort();
      case 'status': return statusBlock();
      case 'ping': return '🏓 pong';
      case 'whoami': {
        const me = userId ? `${speakerName({ author, userId })}(id ${userId})` : author;
        const isOwner = userId && ownerYayId && String(userId) === String(ownerYayId);
        return `🪪 あなた: ${me}${ownerYayId ? (isOwner ? '（=登録オーナー✓）' : '（オーナーではない）') : '（オーナー未登録）'}`;
      }
      case 'iam': {
        // 引数が現在のオーナー表示要求なら状態だけ返す
        if (q === '?' || q === 'status') return ownerYayId ? `🔑 オーナー登録済: ${yayIdToNick(ownerYayId) || 'id ' + ownerYayId}` : '🔓 オーナー未登録（/iam 合言葉 で登録）';
        if (q !== OWNER_SECRET) return '合言葉が違う（/iam <合言葉>）。なりすまし防止のため必要。';
        if (!userId) return 'あなたの Yay ID が取れなかった（チャットから /iam を送って）。';
        ownerYayId = String(userId);
        try { const s = existsSync(CONFIG.stateFile) ? JSON.parse(readFileSync(CONFIG.stateFile, 'utf8')) : { seen: [] }; s.ownerYayId = ownerYayId; writeFileSync(CONFIG.stateFile, JSON.stringify(s, null, 2)); } catch (e) { console.error('owner persist', e.message); }
        console.log('[bot] owner登録: yayId', ownerYayId, yayIdToNick(ownerYayId) || '');
        return `🔓 オーナー登録した（${yayIdToNick(ownerYayId) || 'id ' + ownerYayId}）。以降あなたの発言だけツール全開（ファイル閲覧/編集/Bash）で応じる。他の人は会話のみ。`;
      }
      case 'play':
      case 'queue': {
        if (!q) return renderQueue();           // 引数なし = 番号付き一覧
        let songs = splitSongs(q);              // カンマ/改行区切りで複数曲対応
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
              const r = await startAny(s);
              if (r.ok) started = s; else { queue.push(s); added.push(s); }
            } else { queue.push(s); added.push(s); }
          }
          const head = started ? `▶ 再生: ${qLabel(started)}\n` : '';
          return `${plNote}${head}➕ ${added.length}曲をキューに追加\n` + renderQueue();
        }
        // 単曲: /play 一本化（空いてれば即再生、再生中なら積む）
        const one = songs[0];
        if (!nowQuery && !starting) { const r = await startAny(one); return r.ok ? (plNote || null) : notFoundMsg(one); }
        queue.push(one);
        return `${plNote}➕ キューに追加(${queue.length}): ${qLabel(one)}\n` + renderQueue();
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
      case 'qrepeat': {
        // 引数 on/off で明示、無指定はトグル
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
        if (nowIsSpotify) await spotify.pause().catch(() => {});
        await agora.stopMusic(page); nowQuery = null; nowIsSpotify = false;
        return queue.length ? '⏭ スキップ' : '⏭ スキップ（キュー空）';
      case 'stop':
        queue = []; if (nowIsSpotify) await spotify.pause().catch(() => {});
        await agora.stopMusic(page); nowQuery = null; nowIsSpotify = false;
        return '⏹ 停止（キューも消去）';
      case 'clear': queue = []; return '🧹 キュー消去';
      case 'pause': if (nowIsSpotify) await spotify.pause().catch(() => {}); else await agora.pauseMusic(page); return '⏸ 一時停止';
      case 'resume': if (nowIsSpotify) await spotify.resume().catch(() => {}); else await agora.resumeMusic(page); return '▶ 再開';
      case 'vol': { const r = await agora.setMusicVolume(page, q); if (r?.ok) lastVol = r.vol; return r?.ok ? `🔊 音量 ${r.vol}` : '音量は 0〜100（例: /v 15）'; }
      case 'volup': { const v = Math.min(100, lastVol + 10); const r = await agora.setMusicVolume(page, v); if (r?.ok) lastVol = r.vol; return `🔊 音量 ${r?.vol ?? v}`; }
      case 'voldown': { const v = Math.max(0, lastVol - 10); const r = await agora.setMusicVolume(page, v); if (r?.ok) lastVol = r.vol; return `🔉 音量 ${r?.vol ?? v}`; }
      case 'np': return nowQuery ? `🎵 再生中: ${nowQuery}${queue.length ? ` / 次(${queue.length}): ${queue.slice(0, 3).join(' / ')}` : ''}` : (queue.length ? `📜 キュー(${queue.length}): ${queue.slice(0, 5).join(' / ')}` : '何も流してない');
      case 'loop': { const r = await agora.setLoop(page); return r?.loop ? '🔁 一曲ループON（今の曲を繰り返す）' : '➡ 一曲ループOFF'; }
      case 'live': await agora.playLive(page, q || null); nowQuery = 'live'; return `▶ システム音声配信中${q ? '（' + q + '）' : ''}`;
      case 'dev': { const ds = await agora.listAudioInputs(page); return '🎤 入力: ' + (ds.map((d) => d.label).filter(Boolean).join(' / ') || 'なし'); }
      case 'rec': {
        if (/^(stop|off|止め|終わ|停止|オフ)/.test(q)) {
          const r = await stopCallRecording();
          return r ? (r.conv.ok ? `■ 録音停止→mp3保存(${r.mins}分/${r.conv.kb}KB): ${r.mp3Path.split('/').pop()}` : `■ 停止したがmp3変換失敗: ${r.conv.reason}`) : '録音してない';
        }
        if (/^(save|保存|区切|スナップ|ここまで)/.test(q)) {
          if (!recState?.active) return '録音してない';
          await drainRecToFile();
          const snap = recState.mp3Path.replace(/\.mp3$/, `_snap_${ts2()}.mp3`);
          const c = convertToMp3(recState.webmPath, snap);
          return c.ok ? `💾 ここまでをmp3保存(${c.kb}KB): ${snap.split('/').pop()}（録音継続中）` : `mp3変換失敗: ${c.reason}`;
        }
        if (/^(on|start|開始|再開|始め)/.test(q) || (!q && !recState?.active)) {
          await startCallRecording(process.env.YAY_CALL_ID || 'call');
          return recState?.active ? '● 録音開始' : '録音開始に失敗';
        }
        const st = await agora.recStatus(page);
        return recState?.active ? `🔴 録音中（${Math.round((Date.now() - recState.startedAt) / 60000)}分 / 音源${st?.sources ?? '?'}）: ${recState.webmPath.split('/').pop()}` : '⚪ 録音停止中（/rec on で開始）';
      }
      case 'jingle': {  // 入退室あいさつ ON/OFF（人格・読み上げとは独立）
        const want = q.toLowerCase();
        if (want === '?' || want === 'status') return `🎉 入退室あいさつ: ${jingleOn ? 'ON' : 'OFF'}（声${JC().voice === false ? 'OFF' : 'ON'} / 在室${[...roster.values()].filter((r) => r.present).length}人）`;
        if (['on', 'start', 'オン', '1'].includes(want)) { jingleOn = true; return '🎉 入退室あいさつON（入ってきた人に挨拶する）'; }
        if (['off', 'stop', 'オフ', '0', 'なし'].includes(want)) { jingleOn = false; jingleQueue = []; return '🤫 入退室あいさつOFF'; }
        jingleOn = !jingleOn; if (!jingleOn) jingleQueue = [];
        return jingleOn ? '🎉 入退室あいさつON' : '🤫 入退室あいさつOFF';
      }
      case 'leave': await stopCallRecording(); await agora.leave(page); nowQuery = null; queue = []; return '👋 通話から抜けた（録音はmp3化して保存）';
      case 'mode': {
        const want = q.toLowerCase();
        if (!want || want === '?') return `🎭 人格: ${personaKey || '通常'} / 💬 自発おしゃべり: ${idleChatOn ? 'ON' : 'OFF'}`;
        if (['off', 'normal', 'plain', 'なし', '通常', 'オフ'].includes(want)) return setPersona('');
        const key = PERSONA_ALIAS[want] || (PERSONAS[want] ? want : null);
        if (!key) return `そのモードは無い（使えるの: ${Object.keys(PERSONAS).join(', ')} / off）`;
        return setPersona(key);
      }
      case 'zunda':  // 語尾トグル（自発おしゃべりとは独立）
        return setPersona(personaKey === 'zundamon' ? '' : 'zundamon');
      case 'idle': {  // 自発おしゃべり ON/OFF（人格と独立）
        const want = q.toLowerCase();
        if (want === '?' ) return `💬 自発おしゃべり: ${idleChatOn ? 'ON' : 'OFF'}`;
        const on = ['on', 'start', '開始', 'オン', '1'].includes(want);
        const off = ['off', 'stop', 'なし', 'オフ', '0', '止め', '停止'].includes(want);
        return setIdleChat(on ? true : off ? false : !idleChatOn);
      }
      case 'ttsvol': {  // 読み上げ音量 0-100
        if (!q) return `🔈 読み上げ音量: ${lastTtsVol}（変更は /vv 0-100）`;
        const r = await agora.setTtsVolume(page, q);
        if (r?.ok) lastTtsVol = r.vol;
        return r?.ok ? `🔈 読み上げ音量 ${r.vol}` : '音量は 0〜100（例: /vv 30）';
      }
      case 'voicemode': {  // 声モード切替（normal=元気な普通 / auto=状況自動 / power / sad）
        const w = q.toLowerCase();
        const map = { normal: 'normal', 'ノーマル': 'normal', '普通': 'normal', '元気': 'normal', '基本': 'normal',
          auto: 'auto', '自動': 'auto', 'おまかせ': 'auto',
          power: 'power', 'パワー': 'power', 'パワフル': 'power', 'テンション': 'power',
          sad: 'sad', '悲しい': 'sad', 'かなしい': 'sad', 'しょんぼり': 'sad' };
        if (!w || w === '?') return `🎙 声モード: ${voiceMode}（normal=元気な普通のずんだもん / auto=状況で自動 / power=パワフル / sad=悲しい）。変更: /voicemode auto 等`;
        const m = map[w];
        if (!m) return '声モードは normal / auto / power / sad（例: /voicemode normal）';
        voiceMode = m;
        const desc = { normal: '元気な普通のずんだもん固定', auto: '状況で normal/power/sad を自動選択', power: 'パワフル固定', sad: '悲しい固定' }[m];
        return `🎙 声モード=${voiceMode}（${desc}）`;
      }
      case 'duck': {  // TTS中の音楽残し率 0-100（大きいほど音楽を下げない）
        if (!q) return `🎚 ダッキング(声の時の音楽残し): ${lastDuck}%（変更は /duck 0-100。大=音楽そのまま）`;
        const r = await agora.setDuck(page, q);
        if (r?.ok) lastDuck = r.duck;
        return r?.ok ? `🎚 ダッキング ${r.duck}%（声の時も音楽を ${r.duck}% 残す）` : 'ダッキングは 0〜100（例: /duck 70）';
      }
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
  // 前回の browser/file server を掃除（監視運用で枠を渡り歩く時のリーク防止）。
  try { if (browser) await browser.close(); } catch {}
  try { if (fileServer) fileServer.close(); } catch {}
  browser = null; fileServer = null;

  // 取りこぼし回収（失敗しない仕組みの核）: 通話に入る前＝起動の最初に必ず走らせる。
  //   前回クラッシュ/kill で mp3 化されなかった webm を救う。通話が無くても回収される（冪等・背景）。
  recoverOrphanRecordings();   // await しない＝待ち受けと並行で変換

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
  fileServer = fs.server;
  fileBase = `http://127.0.0.1:${fs.port}`;
  console.log('[bot] file server', fileBase);

  // ★クライアントHTMLは file:// でなく loopback HTTP から開く（PNA 回避＝音が通る。2026-06-07）
  const a = await agora.launchAgora({ headless: !process.env.HEADFUL, pageUrl: `${fileBase}/client` });
  page = a.page; browser = a.browser;
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

  // 初期音量（既定2＝lastVol、YAY_MUSIC_VOL で上書き可）。毎回明示適用して決定論的にする。
  { const r = await agora.setMusicVolume(page, lastVol); console.log('[bot] 初期音量', r?.vol); }

  // join 直後の inbox を一掃（参加前の残/エコーに反応しない）
  try { await agora.drainInbox(page); } catch {}

  const stateExisted = existsSync(CONFIG.stateFile);
  const st0 = loadState();
  const seen = new Set(st0.seen);
  ownerYayId = st0.ownerYayId || process.env.YAY_OWNER_YAYID || CONFIG.ownerYayId || null;
  cmdsEnabled = st0.cmdsEnabled !== false;   // 既定ON。前回 /cmds off のまま落ちても状態を継承
  console.log('[bot] owner(yayId):', ownerYayId || '未登録（/iam ' + OWNER_SECRET + ' で登録）', WATCHING ? `/ 監視=${DISCOVER_UID}（枠に自動入室）` : '/ 自分の通話を待機');
  console.log('[bot] 稼働開始', stateExisted ? '(seen継承)' : '(初回)');
  console.log('[bot] 人格:', personaKey || '通常', '/ 自発おしゃべり:', idleChatOn ? `ON(${IDLE_MIN_MS / 1000}〜${IDLE_MAX_MS / 1000}s)` : 'OFF', '（/zunda 語尾・/idle 自発）');
  console.log('[bot] 入退室あいさつ:', jingleOn ? `ON(名簿${(JC().pollMs || 12000) / 1000}sおき・声${JC().voice === false ? 'OFF' : 'ON'})` : 'OFF', '（/jingle で切替）');

  // 自発おしゃべり用の状態
  const recentLines = [];       // ローリング会話履歴（古→新）
  const pushLine = (s) => { recentLines.push(s); if (recentLines.length > 14) recentLines.shift(); };
  // 返信用文脈: 先頭に「今居る人」を付け、各行頭の名前で発言者を示す（誰が何を言ったか・名前で呼べる）。
  const buildCtx = () => {
    const present = presentNames();
    const head = present.length ? `（今この通話に居る人: ${present.join('、')}。各行頭の「名前:」が発言者で、「（声）」は音声発言。相手は名前で呼んでよい）\n` : '';
    return head + recentLines.slice(-10).join('\n');
  };
  // 自発おしゃべりONで起動した場合は直後に一発目を出す（以降は中スパン）。OFFなら通常待機。
  lastActivityAt = idleChatOn ? Date.now() - IDLE_QUIET_MS - 1 : Date.now();
  nextIdleAt = Date.now();
  // 読み上げ音量を初期反映（env/既定）。publish バス未生成でも S.ttsVol に保持される。
  try { await agora.setTtsVolume(page, lastTtsVol); } catch {}
  // ダッキング率を初期反映（既定70%＝声の時も音楽をしっかり残す）。
  try { const r = await agora.setDuck(page, lastDuck); if (r?.ok) lastDuck = r.duck; } catch {}

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

  // TTS 経路の self-test: YAY_TTS_SELFTEST=1 で join 直後に1回だけ喋る（音が通話に出るか実機確認用）。
  if (process.env.YAY_TTS_SELFTEST && joined.rtc?.ok) {
    await tts.voicevoxAlive();
    console.log('[bot] 🔎 TTS self-test 実行（' + tts.engineName() + '）');
    try {
      const r = await tts.speak('ずんだもんなのだ。声のテスト成功なのだ。', { voice: 'zundamon' });
      if (r.ok && r.file) { const pr = await agora.playTTS(page, agora.fileUrl(fileBase, r.file)); console.log('[bot] self-test playTTS:', JSON.stringify(pr)); }
      else console.error('[bot] self-test TTS 生成失敗', r);
    } catch (e) { console.error('[bot] self-test ERR', e.message); }
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

  // 常時録音（究指示）: join 直後に自動開始。YAY_NO_REC=1 で無効化可。
  if (joined.rtc?.ok && !process.env.YAY_NO_REC) {
    await startCallRecording(process.env.YAY_CALL_ID || creds.conference_id || creds.channel);
  }

  // 監視通話の継続確認用（WATCHING 時のみ使う）
  let watchMiss = 0, lastWatchAt = Date.now();

  for (;;) {
    // 監視運用: 究(えも)の枠が終わった/別枠に移ったら離脱して再探索（次の枠を待つ）。
    //   get_active_call_post はゆらぐので、終了判定は連続 miss で確定（誤離脱防止）。
    if (WATCHING && Date.now() - lastWatchAt > (CONFIG.watchCheckMs || 20000)) {
      lastWatchAt = Date.now();
      const a = await fetchCreds().catch(() => null);   // active(DISCOVER_UID)
      if (a && a.ok && a.conference_id && String(a.conference_id) !== String(creds.conference_id)) {
        watchMiss = 0;
        console.log('[bot] 究が別の枠へ移動→切替（', creds.conference_id, '→', a.conference_id, '）');
        await stopCallRecording(); try { await agora.leave(page); } catch {}
        throw new Error('watched call switched');   // 外側 wrapper が main 再実行→新しい枠へ
      } else if (!a || !a.ok) {
        watchMiss++;
        if (watchMiss >= (CONFIG.watchMissToLeave || 3)) {
          console.log('[bot] 究の枠が終了→離脱して次の枠を待つ（miss', watchMiss, '）');
          await stopCallRecording(); try { await agora.leave(page); } catch {}
          throw new Error('watched call ended');
        }
      } else watchMiss = 0;
    }

    // キュー自動送り: 再生が止まっててキューがあれば次を流す（Spotify/YouTube 両対応）
    if (!starting) {
      try {
        let ended;
        if (nowIsSpotify) {
          // Spotify(live BlackHole)は ended イベントが無いので Web Player の再生状態で判定。
          //   誤検知(瞬間停止/トラック切替)を避けるため連続3回 stopped で「終了」とみなす。
          const ps = await spotify.playbackState().catch(() => null);
          if (ps && ps.ok && !ps.playing) spEndedPolls++; else spEndedPolls = 0;
          ended = spEndedPolls >= 3;
        } else {
          const st = await agora.status(page);
          ended = !st?.nowPlaying;
          spEndedPolls = 0;
        }
        if (ended) {
          if (queue.length) {
            spEndedPolls = 0;
            const next = queue.shift();
            if (queueRepeat) queue.push(next);          // リピートON: 流した曲を末尾へ戻して循環
            const r = await startAny(next);             // タイトル通知は startAny→startTrack/startSpotify 内で実施済み
            console.log('  ▶ next:', r, queueRepeat ? '(repeat)' : '');
          } else if (nowQuery && nowQuery !== 'live') { nowQuery = null; nowIsSpotify = false; spEndedPolls = 0; }
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
        const vname = speakerNameByUuid(u.uid);   // 声の話者名（chat で学習済みなら名前、未学習は「誰か」）
        console.log(`  👂 聞[${vname}]: ${heard}`);
        pushLine(`${vname}（声）: ${heard}`);
        lastActivityAt = Date.now();
        if (canReply()) {
          const context = buildCtx();
          try {
            const out = await emoccReply(context, { system: personaSys });
            if (out.action) { console.log('  🎬 ACTION(声):', out.action); const ar = await handleCommand(out.action, u.uid, uuidToYayId.get(String(u.uid))); if (ar) await sendYayChat(page, ar).catch(() => {}); }
            const reply = (out.reply || '').replace(/^[!\/]\S*\s*/, '').trim();
            if (reply) { await sendYayChat(page, reply); markReplied(); pushLine(`自分: ${reply}`); console.log('  → 声返信:', reply); await sayOut(reply); }
          } catch (e) { console.error('voice reply err', e.message); }
        }
      }
    }

    // 自発おしゃべり（/idle ON時のみ・人格とは独立）: 場が静かなら中スパンで自分から一言
    if (idleChatOn && IDLE_MAX_MS > 0 && Date.now() >= nextIdleAt
        && (Date.now() - lastActivityAt) > IDLE_QUIET_MS && canReply()) {
      try {
        const ctx = buildCtx();
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

    await drainRecToFile();   // 録音チャンクをファイルへ追記（常時）

    // 入退室ジングル: 名簿を周期取得して差分→挨拶（throttle は関数内）
    try { await pollMembersAndDiff(); } catch (e) { console.error('jingle poll', e.message); }
    try { await drainJingle(); } catch (e) { console.error('jingle drain', e.message); }

    let raw = [];
    try { raw = await agora.drainInbox(page); } catch (e) { console.error('drain err', e.message); }
    const msgs = raw.map(parseMsg).filter((m) => m.text);
    // 自己除外: publisher uuid でも Yay id でも自分なら弾く（取りこぼし二重ガード）。
    const fresh = msgs.filter((m) => !seen.has(m.id) && m.author !== SELF_RTM && String(m.userId || '') !== String(SELF_UID));
    fresh.forEach((m) => seen.add(m.id));
    // 名前学習: chat には送信者 Yay id が乗る＝publisher uuid ↔ Yay id を覚える（声の話者名解決に効く）。
    fresh.forEach((m) => { if (m.userId && m.author) uuidToYayId.set(String(m.author), String(m.userId)); });

    if (fresh.length) {
      lastActivityAt = Date.now();
      const ts = new Date().toLocaleTimeString('ja-JP');
      fresh.forEach((m) => { const nm = speakerName(m); console.log(`[${ts}] 新着 ${nm}: ${m.text}`); pushLine(`${nm}: ${m.text}`); });
      const isOwner = (m) => !!ownerYayId && String(m.userId || '') === String(ownerYayId);
      const nlHandled = new Set();
      for (const m of fresh) {
        let mr = await runCommands(m.text, m.author, m.userId);
        // オーナー本人の自然言語は音楽コマンドに翻訳して実行（「○○流して」「止めて」「Spotifyで○○」等）
        if (mr === null && isOwner(m) && !/^[!\/]/.test(m.text)) {
          const nl = nlToCommand(m.text);
          if (nl) { nlHandled.add(m.id); console.log('  🗣→cmd', nl); mr = await handleCommand(nl, m.author, m.userId); }
        }
        // コマンド応答は究の明示要求＝必ず返す（連投ガードは会話返信だけに掛ける。
        //   ここを canReply で塞ぐと /q /h /st 等がクールダウン中に握り潰され「効かない」に見える）。
        if (mr) { await sendYayChat(page, mr).catch((e) => console.error('send', e.message)); console.log('  ♪', mr); }
      }
      const conv = fresh.filter((m) => !/^[!\/]/.test(m.text) && !nlHandled.has(m.id));
      if (conv.length && canReply()) {
        const context = buildCtx();
        // 話者ガード: この返信が応じる発言が全てオーナー本人の時だけツール全開。
        //   他人が混じる/オーナー未登録なら会話のみ（ファイル/Bash 不可）。
        // 高速化(2026-06-06): 通常会話は tools=false の軽量パス（CLAUDE.md 読込無し＝最速）。
        //   ファイル/コード/開発依頼が明確な時だけ tools 全開に昇格（cwd=Downloads で重い）。
        const ownerOnly = !!ownerYayId && conv.every(isOwner);
        const tools = ownerOnly && conv.some((m) => wantsTools(m.text));
        try {
          const out = await emoccReply(context, { system: personaSys, tools });
          // LLM が音楽操作を判断したら ACTION 行を実体コマンドとして実行（/play 等）
          if (out.action) { console.log('  🎬 ACTION:', out.action); const lm = conv[conv.length - 1]; const ar = await handleCommand(out.action, lm?.author, lm?.userId); if (ar) await sendYayChat(page, ar).catch(() => {}); }
          const reply = (out.reply || '').replace(/^[!\/]\S*\s*/, '').trim();
          if (reply) { await sendYayChat(page, reply); markReplied(); pushLine(`自分: ${reply}`); lastActivityAt = Date.now(); console.log('  → 返信:', reply); await sayOut(reply); }
          else if (!out.action) console.log('  → [skip]');
        } catch (e) { console.error('reply err', e.message); }
      } else if (conv.length) console.log('  → 連投ガードで保留');
      saveState({ seen: [...seen].slice(-2000), ownerYayId, cmdsEnabled });
    }
    await sleep(CONFIG.pollMs);
  }
}

process.on('unhandledRejection', (e) => console.error('unhandledRejection:', e?.message || e));
// 停止シグナルで録音を mp3 化してから落ちる（webm は逐次追記済なので最悪でも素材は残る）。
// SIGHUP も捕捉（tmux kill-session / 端末切断）。停止時 mp3 化はベストエフォート、
//   取りこぼしても次回起動の recoverOrphanRecordings() が必ず救う（二重の安全網）。
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(sig, async () => { try { await stopCallRecording(); } catch {} process.exit(0); });
(async () => {
  for (;;) {
    try { await main(); }
    catch (e) {
      console.error('[bot] 落ちた→5秒後再起動:', e.message);
      try { await stopCallRecording(); } catch {}   // 切断ごとに1ファイル確定（mp3化）
      await sleep(5000);
    }
  }
})();
