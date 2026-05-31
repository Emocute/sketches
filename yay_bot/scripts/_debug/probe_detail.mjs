import { chromium } from 'playwright';
const browser = await chromium.connectOverCDP('http://localhost:9222');
const ctx = browser.contexts()[0];
let page = ctx.pages().find((p) => /conference/.test(p.url())) || ctx.pages().find((p) => /yay\.space/.test(p.url()));
const out = await page.evaluate(() => {
  const item = document.querySelector('.Messages__item');
  const form = document.querySelector('.CallChatReplyForm');
  const items = [...document.querySelectorAll('.Messages__item')].slice(-3).map((el) => el.outerHTML.slice(0, 400));
  // モーダルが開いてないか
  const modalOpen = [...document.querySelectorAll('[class*="Modal"],[class*="ConfirmBox"]')].filter((el) => {
    const r = el.getBoundingClientRect(); const st = getComputedStyle(el);
    return r.width > 50 && r.height > 50 && st.display !== 'none' && st.visibility !== 'hidden';
  }).map((el) => el.className.toString().split(' ')[0]);
  return {
    itemHTML: item ? item.outerHTML.slice(0, 600) : null,
    formHTML: form ? form.outerHTML.slice(0, 600) : null,
    lastItems: items,
    msgCount: document.querySelectorAll('.Messages__item').length,
    visibleModals: [...new Set(modalOpen)],
  };
});
console.log('msgCount:', out.msgCount);
console.log('visibleModals:', JSON.stringify(out.visibleModals));
console.log('\n=== item HTML ===\n', out.itemHTML);
console.log('\n=== form HTML ===\n', out.formHTML);
console.log('\n=== last items ===\n', out.lastItems.join('\n---\n'));
await browser.close();
