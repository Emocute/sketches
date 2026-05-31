// 通話ツールバーのチャットボタンを特定→開く→チャット内部DOMを解析（CDP接続・窓は閉じない）
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';
const __dir = path.dirname(fileURLToPath(import.meta.url));
const ASSETS = path.join(__dir, '..', 'assets');

const browser = await chromium.connectOverCDP('http://localhost:9222');
const ctx = browser.contexts()[0];
let page = ctx.pages().find((p) => /conference/.test(p.url())) || ctx.pages().find((p) => /yay\.space/.test(p.url()));
await page.bringToFront().catch(() => {});

// ツールバー項目の全クラス + 内側 svg のヒントを列挙
const toolbar = await page.evaluate(() => {
  const items = [...document.querySelectorAll('[class*="toolbar__item"], [class*="Toolbar"], button')];
  return items.slice(0, 60).map((el, i) => ({
    i, cls: (el.className || '').toString(),
    svg: el.querySelector('svg')?.outerHTML?.slice(0, 60) || null,
    use: el.querySelector('use')?.getAttribute('xlink:href') || el.querySelector('use')?.getAttribute('href') || null,
    img: el.querySelector('img')?.src?.slice(-40) || null,
  })).filter((x) => /toolbar|Toolbar/.test(x.cls));
});
console.log('=== toolbar items ===');
console.log(JSON.stringify(toolbar, null, 1));

// チャットらしき項目をクリック（class に chat/comment/message、無ければ何もしない）
const chatSel = await page.evaluate(() => {
  const cand = [...document.querySelectorAll('[class*="toolbar__item"]')];
  const hit = cand.find((el) => /chat|comment|message|talk/i.test(el.className.toString()) || /chat|comment|message/i.test(el.querySelector('svg')?.outerHTML || ''));
  if (hit) { hit.setAttribute('data-yaybot', 'chat'); return true; }
  return false;
});
if (chatSel) {
  await page.click('[data-yaybot="chat"]').catch(() => {});
  await page.waitForTimeout(1500);
  console.log('chat ボタンをクリックした');
} else {
  console.log('chat ボタンをクラス名で特定できず（toolbar 一覧から人手で判定要）');
}

// チャットパネル内部を再解析
const probe = await page.evaluate(() => {
  const freq = {};
  document.querySelectorAll('*').forEach((el) => {
    if (el.children.length === 0 && el.textContent && el.textContent.trim().length > 0) {
      const cls = el.className && el.className.toString ? el.className.toString().split(' ').slice(0, 2).join('.') : '';
      const k = el.tagName.toLowerCase() + (cls ? '.' + cls : '');
      freq[k] = (freq[k] || 0) + 1;
    }
  });
  const top = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 30);
  const inputs = [...document.querySelectorAll('textarea, input[type="text"], [contenteditable="true"], [role="textbox"]')]
    .filter((el) => !/recaptcha/.test(el.className))
    .map((el) => ({ tag: el.tagName.toLowerCase(), ph: el.placeholder || null, ce: el.getAttribute('contenteditable'), role: el.getAttribute('role'), cls: (el.className || '').toString().slice(0, 90) }));
  // class に message/comment/timeline/chat を含む要素
  const msgish = {};
  document.querySelectorAll('[class*="essage"],[class*="omment"],[class*="imeline"],[class*="hat"]').forEach((el) => {
    const c = el.className.toString().split(' ')[0]; msgish[c] = (msgish[c] || 0) + 1;
  });
  return { top, inputs, msgish: Object.entries(msgish).sort((a, b) => b[1] - a[1]).slice(0, 20) };
});
console.log('=== 末端テキスト class 頻度 ===');
console.log(JSON.stringify(probe.top));
console.log('=== message/comment/chat 系 class ===');
console.log(JSON.stringify(probe.msgish));
console.log('=== 入力欄候補 ===');
console.log(JSON.stringify(probe.inputs, null, 1));

await page.screenshot({ path: path.join(ASSETS, '_chat_view.png') });
console.log('screenshot -> assets/_chat_view.png');
await browser.close();
