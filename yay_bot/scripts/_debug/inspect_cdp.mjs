// CDP 接続で「今開いているページ」を解析（窓は閉じない・究の操作を邪魔しない）
// 用法: node scripts/inspect_cdp.mjs
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __dir = path.dirname(fileURLToPath(import.meta.url));
const ASSETS = path.join(__dir, '..', 'assets');

const browser = await chromium.connectOverCDP('http://localhost:9222');
const ctx = browser.contexts()[0];
const pages = ctx.pages();
// 一番最近アクティブそうなページ（yay を含むもの優先）
let page = pages.find((p) => /yay\.space/.test(p.url())) || pages[pages.length - 1] || pages[0];
await page.bringToFront().catch(() => {});

console.log('open pages:', pages.map((p) => p.url()));
console.log('analyzing :', page.url());
console.log('title     :', await page.title());

const probe = await page.evaluate(() => {
  const freq = {};
  document.querySelectorAll('*').forEach((el) => {
    if (el.children.length === 0 && el.textContent && el.textContent.trim().length > 1) {
      const cls = el.className && el.className.toString ? el.className.toString().split(' ').slice(0, 2).join('.') : '';
      const k = el.tagName.toLowerCase() + (cls ? '.' + cls : '');
      freq[k] = (freq[k] || 0) + 1;
    }
  });
  const top = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 30);
  const inputs = [...document.querySelectorAll('textarea, input[type="text"], [contenteditable="true"], [role="textbox"]')].map((el) => ({
    tag: el.tagName.toLowerCase(), type: el.type || null, ph: el.placeholder || null,
    ce: el.getAttribute('contenteditable'), role: el.getAttribute('role'),
    cls: (el.className || '').toString().slice(0, 90),
  }));
  const buttons = [...document.querySelectorAll('button, [role="button"]')].slice(0, 40).map((el) => ({
    aria: el.getAttribute('aria-label'), title: el.title || null,
    txt: (el.textContent || '').trim().slice(0, 20), cls: (el.className || '').toString().slice(0, 60),
  }));
  return { topTextClasses: top, inputs, buttons };
});

console.log('--- 末端テキスト要素 class 頻度（メッセージ行候補）---');
console.log(JSON.stringify(probe.topTextClasses));
console.log('--- 入力欄候補 ---');
console.log(JSON.stringify(probe.inputs, null, 1));
console.log('--- ボタン候補（送信ボタン探し）---');
console.log(JSON.stringify(probe.buttons, null, 1));

await page.screenshot({ path: path.join(ASSETS, '_call_view.png') });
console.log('screenshot -> assets/_call_view.png');
await browser.close(); // CDP 接続だけ切る（Chrome 自体は閉じない）
