// Yay トランスポート層（CDP 接続。窓は閉じない＝ロック衝突なし）
import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';

const S = CONFIG.selectors;

export async function connectYay() {
  const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
  const all = browser.contexts().flatMap((c) => c.pages());
  const page =
    all.find((p) => /conference/.test(p.url())) ||
    all.find((p) => /yay\.space/.test(p.url())) ||
    all[0];
  const ctx = page ? page.context() : browser.contexts()[0];
  return { browser, ctx, page };
}

// チャットパネルが閉じてたら開く
export async function openChatPanel(page) {
  const ready = await page.$(S.inputBox);
  if (!ready) {
    await page.click(S.chatToggle).catch(() => {});
    await page.waitForTimeout(1200);
  }
}

// ★メッセージ取りこぼし対策：ページに常駐フックを注入し、Yay が描画した瞬間に全メッセージを
// window.__yayMsgBuf に溜める。Yay の通話チャットは仮想リストで古い行を DOM から消すため、
// 7秒ごとのポーリングだけだと消えた行を読めない。MutationObserver で描画イベントを全捕捉する。
// 冪等（再注入してもOK）。通話に入り直してもパネル開閉のたびに呼んで貼り直す。
export async function installCapture(page) {
  await page.evaluate((sel) => {
    const extract = (row) => {
      const a = row.querySelector(sel.messageImg);
      const href = a?.getAttribute('href') || '';
      const alt = row.querySelector(sel.messageImg + ' img')?.getAttribute('alt') || '';
      const name = alt.replace(/のカバー写真$/, '').trim();
      const author = name || (href ? 'user' + href.replace('/user', '') : '?');
      const text = row.querySelector(sel.messageText)?.textContent?.trim() || '';
      const time = row.querySelector(sel.messageTime)?.textContent?.trim() || '';
      if (!text || text === 'このメッセージは削除されました') return null;
      return { id: `${href}|${time}|${text}`, href, author, text, time };
    };
    if (!window.__yayMsgBuf) window.__yayMsgBuf = [];
    if (!window.__yaySeenIds) window.__yaySeenIds = new Set();
    const push = (m) => {
      if (!m || window.__yaySeenIds.has(m.id)) return;
      window.__yaySeenIds.add(m.id);
      window.__yayMsgBuf.push(m);
      if (window.__yayMsgBuf.length > 800) window.__yayMsgBuf.splice(0, window.__yayMsgBuf.length - 800);
    };
    const sweep = () => document.querySelectorAll(sel.messageRow).forEach((r) => push(extract(r)));
    sweep(); // 既存行を取り込む
    if (window.__yayCapObs) return; // observer は1回だけ
    // 通話画面はタイマー等で頻繁に更新されるのでスロットル（最大250msに1回 sweep）
    let pending = false;
    const throttled = () => { if (pending) return; pending = true; setTimeout(() => { pending = false; sweep(); }, 250); };
    // チャットの親に絞れれば軽い。無ければ body 全体（フォールバック）
    const target = document.querySelector('.Messages__wrapper') || document.querySelector('.CallChatRoom') || document.body;
    window.__yayCapObs = new MutationObserver(throttled);
    window.__yayCapObs.observe(target, { childList: true, subtree: true, characterData: true });
  }, S);
}

export async function readMessages(page) {
  // バッファ常駐を保証してから、溜まった全メッセージ（消えた行含む）を時系列で返す
  await installCapture(page);
  return page.evaluate((sel) => {
    return (window.__yayMsgBuf || [])
      .filter((m) => m.text && m.text !== 'このメッセージは削除されました');
  }, S);
}

// 通話音声を「音楽が部屋に流れる」状態に保証する（再生のたびに自動で呼ぶ）。
//   1) 通話マイク入力 = BlackHole 2ch（音楽ブラウザの出力先）
//   2) マイクのミュート解除
// 冪等：既に正しければ何もしない。戻り値で各ステップの状態を返す（診断用）。
export async function ensureCallAudio(page) {
  if (!/conference/.test(page.url())) return { ok: false, reason: '通話画面ではない', url: page.url() };

  // 通話音声設定を開いて <select> から BlackHole を選ぶ
  await page.evaluate(() => document.querySelector('.ConferenceCallScreen__sound_management')?.click());
  await page.waitForTimeout(900);
  const mic = await page.evaluate(async () => {
    const selects = [...document.querySelectorAll('select')];
    for (const s of selects) {
      const opt = [...s.options].find((o) => /BlackHole/i.test(o.textContent));
      if (opt) {
        if (s.value !== opt.value) {
          s.value = opt.value;
          s.dispatchEvent(new Event('change', { bubbles: true }));
          return { set: true, label: opt.textContent.trim() };
        }
        return { set: 'already', label: opt.textContent.trim() };
      }
    }
    return { set: false, reason: 'BlackHole の入力 select が無い' };
  });
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(400);

  // ミュート解除
  const muteState = await page.evaluate(() => {
    const muted = document.querySelector('.ConferenceCallScreen__toolbar__item--mic-muted');
    if (muted) { muted.click(); return 'unmuted(解除した)'; }
    return document.querySelector('.ConferenceCallScreen__toolbar__item--mic') ? 'already-unmuted' : 'unknown';
  });
  return { ok: mic.set !== false, mic, mute: muteState };
}

export async function postMessage(page, text) {
  await openChatPanel(page);
  const box = page.locator(S.inputBox).last();
  await box.click();
  await box.fill(text.slice(0, 255));
  await page.locator(S.sendButton).last().click().catch(async () => {
    await page.keyboard.press('Enter');
  });
  await page.waitForTimeout(400);
}
