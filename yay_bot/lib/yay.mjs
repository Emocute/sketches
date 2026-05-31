// Yay トランスポート層（CDP 接続。窓は閉じない＝ロック衝突なし）
import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';

const S = CONFIG.selectors;

export async function connectYay() {
  const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
  const ctx = browser.contexts()[0];
  const page =
    ctx.pages().find((p) => /conference/.test(p.url())) ||
    ctx.pages().find((p) => /yay\.space/.test(p.url())) ||
    ctx.pages()[0];
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

export async function readMessages(page) {
  return page.evaluate((sel) => {
    return [...document.querySelectorAll(sel.messageRow)]
      .map((row) => {
        const a = row.querySelector(sel.messageImg);
        const href = a?.getAttribute('href') || '';
        const alt = row.querySelector(sel.messageImg + ' img')?.getAttribute('alt') || '';
        const name = alt.replace(/のカバー写真$/, '').trim();
        const author = name || (href ? 'user' + href.replace('/user', '') : '?');
        const text = row.querySelector(sel.messageText)?.textContent?.trim() || '';
        const time = row.querySelector(sel.messageTime)?.textContent?.trim() || '';
        return { id: `${href}|${time}|${text}`, href, author, text, time };
      })
      .filter((m) => m.text && m.text !== 'このメッセージは削除されました');
  }, S);
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
