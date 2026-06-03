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

// yay_api.py を叩いて creds JSON を得る（最終行が JSON）
function fetchCreds() {
  const args = process.env.YAY_CALL_ID ? ['creds', String(process.env.YAY_CALL_ID)] : ['active', SELF_UID];
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

async function handleMusic(text) {
  const mm = text.match(/^\/(play|yt|stop|pause|resume)\s*(.*)/i);
  if (!mm) return null;
  const [, cmdRaw, q] = mm; const cmd = cmdRaw.toLowerCase();
  try {
    if (cmd === 'stop') { await agora.stopMusic(page); return '⏸ 停止'; }
    if (cmd === 'pause') { await agora.pauseMusic(page); return '⏸ 一時停止'; }
    if (cmd === 'resume') { await agora.resumeMusic(page); return '▶ 再開'; }
    if (!q.trim()) return '曲名を入れて（例: /play 曲名）';
    const r = await music.resolve(q);
    const url = r.directUrl || agora.fileUrl(fileBase, r.path);
    await agora.playUrl(page, url);
    return `▶ ${q} を通話に流してる${r.cached ? '（cache）' : ''}`;
  } catch (e) { return `再生失敗: ${e.message}`; }
}

async function main() {
  console.log('[bot] creds 取得中…');
  creds = await fetchCreds();
  if (!creds.ok) throw new Error('creds 取得失敗: ' + JSON.stringify(creds));
  console.log('[bot] creds ok channel=%s uid=%s rtm=%s', creds.channel, creds.uid, creds.rtm_token ? 'yes' : 'no');

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

  const stateExisted = existsSync(CONFIG.stateFile);
  const seen = new Set(loadState().seen);
  console.log('[bot] 稼働開始', stateExisted ? '(seen継承)' : '(初回)');

  for (;;) {
    let raw = [];
    try { raw = await agora.drainInbox(page); } catch (e) { console.error('drain err', e.message); }
    const msgs = raw.map(parseMsg).filter((m) => m.text);
    const fresh = msgs.filter((m) => !seen.has(m.id) && m.author !== SELF_UID);
    fresh.forEach((m) => seen.add(m.id));

    if (fresh.length) {
      const ts = new Date().toLocaleTimeString('ja-JP');
      fresh.forEach((m) => console.log(`[${ts}] 新着 ${m.author}: ${m.text}`));
      for (const m of fresh) {
        const mr = await handleMusic(m.text);
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
