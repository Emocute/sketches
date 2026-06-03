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

const PY = fileURLToPath(new URL('./.venv/bin/python', import.meta.url));
const API = fileURLToPath(new URL('./yay_api.py', import.meta.url));
const SELF_UID = String(process.env.YAY_SELF_UID || '11320230');
// なりきり人格（YAY_PERSONA=zundamon 等が初期値）。チャットから /mode で実行時切替できる。
let personaKey = String(process.env.YAY_PERSONA || '').toLowerCase();
let personaSys = PERSONAS[personaKey] || undefined;
// 人格名の別名（日本語/略称 → canonical key）
const PERSONA_ALIAS = { zunda: 'zundamon', zundamon: 'zundamon', 'ずんだ': 'zundamon', 'ずんだもん': 'zundamon' };
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
  help:   ['help', 'h', '?'],
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
};
const ALIAS = {}; for (const [k, vs] of Object.entries(CMD)) for (const v of vs) ALIAS[v] = k;
const HELP = [
  '🎧 コマンド一覧',
  '/p 曲 = 今すぐ再生',
  '/q 曲 = キューに追加',
  '/s = 次へ  /x = 停止  /ps = 一時停止  /r = 再開',
  '/v 0-100 = 音量  /np = 再生中  /l = ループ',
  '/lv = システム音声  /d = 入力  /c = キュー消去',
  '/zunda = ずんだもんON/OFF  /mode off = 通常',
  '/h = ヘルプ',
].join('\n');

// 人格の実行時切替（再起動不要）。ON にしたら起動直後と同じく一発目を即出す。
function setPersona(key) {
  personaKey = key || '';
  personaSys = personaKey ? PERSONAS[personaKey] : undefined;
  if (personaSys) { lastActivityAt = Date.now() - IDLE_QUIET_MS - 1; nextIdleAt = Date.now(); return `🎭 ${personaKey} モードON（自発おしゃべり ${IDLE_MIN_MS / 1000}〜${IDLE_MAX_MS / 1000}s）`; }
  return '🎭 通常モードに戻した（自発おしゃべりOFF）';
}

// 1曲を解決→publish（real-time）
async function startTrack(query) {
  starting = true;
  try {
    const r = await music.resolveStreamUrl(query);
    await agora.playUrl(page, agora.streamUrl(fileBase, r.url));
    nowQuery = query;
    return `▶ ${query}`;
  } finally { starting = false; }
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
      case 'help': return HELP;
      case 'ping': return '🏓 pong';
      case 'play':
        if (!q) return '曲名を入れて（例: /p 曲名）';
        return await startTrack(q);
      case 'queue':
        if (!q) return queue.length ? `📜 キュー(${queue.length}): ${queue.slice(0, 5).join(' / ')}` : 'キューは空';
        queue.push(q);
        if (!nowQuery && !starting) return await startTrack(queue.shift());
        return `➕ 追加(${queue.length}): ${q}`;
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
      case 'loop': { const r = await agora.setLoop(page); return r?.loop ? '🔁 ループON' : '➡ ループOFF'; }
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

  for (;;) {
    // キュー自動送り: 再生が止まっててキューがあれば次を流す
    if (!starting) {
      try {
        const st = await agora.status(page);
        if (!st?.nowPlaying) {
          if (queue.length) {
            const r = await startTrack(queue.shift());
            console.log('  ▶ next:', r);
            if (canReply()) { await sendYayChat(page, r).catch(() => {}); markReplied(); }
          } else if (nowQuery && nowQuery !== 'live') { nowQuery = null; }
        }
      } catch {}
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
          if (reply) { await sendYayChat(page, reply); markReplied(); pushLine(`自分: ${reply}`); lastActivityAt = Date.now(); console.log('  → 返信:', reply); }
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
