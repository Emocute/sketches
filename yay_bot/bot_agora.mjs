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
import { emoccReply } from './lib/claude.mjs';
import * as agora from './lib/agora.mjs';
import * as music from './lib/music_agora.mjs';

const PY = fileURLToPath(new URL('./.venv/bin/python', import.meta.url));
const API = fileURLToPath(new URL('./yay_api.py', import.meta.url));
const SELF_UID = String(process.env.YAY_SELF_UID || '11320230');
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

// RTM の生メッセージ → {id, author, text}。形式未知なので寛容にパース（スパイクで要調整）。
function parseMsg(m) {
  let text = m.message, author = String(m.publisher ?? '?');
  if (typeof text !== 'string') { try { text = JSON.stringify(text); } catch { text = String(text); } }
  // JSONで包まれている場合は本文フィールドを拾う
  try {
    const j = JSON.parse(text);
    if (j && typeof j === 'object') text = j.text ?? j.message ?? j.content ?? j.body ?? text;
  } catch {}
  text = String(text || '').trim();
  return { id: `${author}|${m.ts}|${text}`, author, text };
}

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
};
const ALIAS = {}; for (const [k, vs] of Object.entries(CMD)) for (const v of vs) ALIAS[v] = k;
const HELP =
  '🎧 /p 曲=今すぐ /q 曲=追加 /s=次 /x=停止 /ps=一時停止 /r=再開 ' +
  '/v 0-100=音量 /np=再生中 /l=ループ /lv=システム音声 /d=入力 /c=キュー消去 /h=help';

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

  // 初期音量（既定15、YAY_MUSIC_VOL で上書き可）
  if (process.env.YAY_MUSIC_VOL) { const r = await agora.setMusicVolume(page, process.env.YAY_MUSIC_VOL); console.log('[bot] 初期音量', r?.vol); }

  const stateExisted = existsSync(CONFIG.stateFile);
  const seen = new Set(loadState().seen);
  console.log('[bot] 稼働開始', stateExisted ? '(seen継承)' : '(初回)');

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
            if (canReply()) { await agora.sendChat(page, r).catch(() => {}); markReplied(); }
          } else if (nowQuery && nowQuery !== 'live') { nowQuery = null; }
        }
      } catch {}
    }

    let raw = [];
    try { raw = await agora.drainInbox(page); } catch (e) { console.error('drain err', e.message); }
    const msgs = raw.map(parseMsg).filter((m) => m.text);
    const fresh = msgs.filter((m) => !seen.has(m.id) && m.author !== SELF_UID);
    fresh.forEach((m) => seen.add(m.id));

    if (fresh.length) {
      const ts = new Date().toLocaleTimeString('ja-JP');
      fresh.forEach((m) => console.log(`[${ts}] 新着 ${m.author}: ${m.text}`));
      for (const m of fresh) {
        const mr = await handleCommand(m.text);
        if (mr && canReply()) { await agora.sendChat(page, mr).catch((e) => console.error('send', e.message)); markReplied(); console.log('  ♪', mr); }
      }
      const conv = fresh.filter((m) => !/^[!\/]/.test(m.text));
      if (conv.length && canReply()) {
        const context = msgs.filter((m) => !/^[!\/]/.test(m.text)).slice(-10)
          .map((m) => `${m.author === SELF_UID ? 'Emo Claude(自分)' : m.author}: ${m.text}`).join('\n');
        try {
          let reply = (await emoccReply(context)).replace(/^[!\/]\S*\s*/, '').trim();
          if (reply) { await agora.sendChat(page, reply); markReplied(); console.log('  → EmoCC:', reply); }
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
