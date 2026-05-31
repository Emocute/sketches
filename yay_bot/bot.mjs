// yay_bot メインループ（簡易版 v1）
// 起動: YAY_CHAT_URL=<url> node bot.mjs
//   1) Yay を開きログイン確認 → チャットへ
//   2) ポーリングで新着検出 → EmoCC 返信を投稿（連投ガード）
//   3) "/play <曲>" / "/yt <曲>" / "/sp <曲>" を音楽指示として処理
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { CONFIG } from './config.mjs';
import { connectYay, openChatPanel, readMessages, postMessage } from './lib/yay.mjs';
import { emoccReply } from './lib/claude.mjs';
import * as music from './lib/music.mjs';

const loadState = () => (existsSync(CONFIG.stateFile) ? JSON.parse(readFileSync(CONFIG.stateFile, 'utf8')) : { seen: [] });
const saveState = (s) => writeFileSync(CONFIG.stateFile, JSON.stringify(s, null, 2));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let replyTimes = [];
let lastReplyAt = 0;
function canReply() {
  const now = Date.now();
  replyTimes = replyTimes.filter((t) => now - t < 60000);
  if (now - lastReplyAt < (CONFIG.replyCooldownMs || 0)) return false; // クールダウン
  return replyTimes.length < CONFIG.maxRepliesPerMin;
}
function markReplied() { const t = Date.now(); replyTimes.push(t); lastReplyAt = t; }

async function handleMusic(text) {
  const m = text.match(/^\/(play|yt|sp)\s+(.+)/i);
  if (!m) return null;
  const [, cmd, q] = m;
  try {
    if (!music.__connected) { await music.connectMusic(); music.__connected = true; }
    // 既定は Spotify（Premium=広告ゼロ）。/yt の時だけ YouTube
    const useYT = cmd.toLowerCase() === 'yt';
    const r = useYT ? await music.playYouTube(q) : await music.playSpotify(q);
    return `▶ ${r.service}: ${q}${r.route?.ok ? '（通話へ）' : '（音声経路NG: ' + (r.route?.reason || '') + '）'}`;
  } catch (e) {
    return `再生失敗: ${e.message}`;
  }
}

let browserRef, page;
async function connect() {
  const c = await connectYay();
  browserRef = c.browser;
  page = c.page;
  await openChatPanel(page);
  console.log('[bot] 接続:', page.url());
}

async function main() {
  await connect();
  const stateExisted = existsSync(CONFIG.stateFile);
  const seen = new Set(loadState().seen);
  // 初回起動のみ「直近1件以外」を既読化（過去ログ一斉返信を防ぎつつ最新は拾う）。
  // 再起動時は永続 seen を信頼 → ダウン中に来た新着もちゃんと返す。
  if (!stateExisted) {
    try { (await readMessages(page)).slice(0, -1).forEach((m) => seen.add(m.id)); } catch {}
  }
  console.log('[bot] 稼働開始', stateExisted ? '(seen 継承)' : '(初回)');
  let idleTicks = 0;

  for (;;) {
    let msgs = null;
    try {
      await openChatPanel(page); // パネルが閉じてたら毎回開け直す（無言化防止）
      msgs = await readMessages(page);
    } catch (e) {
      console.error('read err → 再接続:', e.message);
      try { await browserRef?.close(); } catch {}
      try { await connect(); } catch (e2) { console.error('reconnect 失敗:', e2.message); }
      await sleep(CONFIG.pollMs);
      continue;
    }
    // 自分(Emo Claude)の投稿は user id で確実に無視（自己対話ループ防止）
    const fresh = msgs.filter((m) => !seen.has(m.id) && m.href !== CONFIG.selfUserHref);
    fresh.forEach((m) => seen.add(m.id));

    if (fresh.length) {
      idleTicks = 0;
      const ts = new Date().toLocaleTimeString('ja-JP');
      fresh.forEach((m) => console.log(`[${ts}] 新着 ${m.author}: ${m.text}`));
      // 音楽コマンド(/play 等)を先に処理
      for (const m of fresh) {
        const musicMsg = await handleMusic(m.text);
        if (musicMsg && canReply()) { await postMessage(page, musicMsg); markReplied(); console.log('  ♪', musicMsg); }
      }
      // 会話返信: 「/」「!」始まり（コマンド類）は会話扱いしない
      const conversational = fresh.filter((m) => !/^[!\/]/.test(m.text));
      if (conversational.length && canReply()) {
        // 文脈はコマンド行(! /)を除いた直近10件（モデルのコマンド復唱を防ぐ）
        const context = msgs
          .filter((m) => !/^[!\/]/.test(m.text))
          .slice(-10)
          .map((m) => `${m.href === CONFIG.selfUserHref ? 'Emo Claude(自分)' : m.author || '?'}: ${m.text}`)
          .join('\n');
        try {
          let reply = await emoccReply(context);
          reply = reply.replace(/^[!\/]\S*\s*/, '').trim(); // 先頭のコマンドエコー除去
          if (reply) {
            await postMessage(page, reply);
            markReplied();
            console.log('  → EmoCC:', reply);
          } else {
            console.log('  → [skip]（黙る判断）');
          }
        } catch (e) { console.error('  reply err', e.message); }
      } else if (conversational.length) {
        console.log('  → 連投ガードで保留');
      }
      saveState({ seen: [...seen].slice(-2000) });
    } else {
      idleTicks++;
      if (idleTicks % 20 === 0) console.log(`[${new Date().toLocaleTimeString('ja-JP')}] 生存中（待機 ${idleTicks} tick）`);
    }
    await sleep(CONFIG.pollMs); // 常に一定間隔（バックオフ無し＝常に応答）
  }
}

process.on('unhandledRejection', (e) => console.error('unhandledRejection:', e?.message || e));
process.on('uncaughtException', (e) => console.error('uncaughtException:', e?.message || e));

async function run() {
  for (;;) {
    try {
      await main();
    } catch (e) {
      console.error('[bot] main 落ちた → 3秒後に再起動:', e.message);
      await sleep(3000);
    }
  }
}
run();
