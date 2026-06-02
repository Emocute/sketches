// 「ログイン」を押して X OAuth 導線を露出させ調べる。
import { chromium } from 'playwright';
const b = await chromium.connectOverCDP('http://127.0.0.1:9222');
const ctx = b.contexts()[0];
let page = ctx.pages().find((p) => /yay\.space/.test(p.url())) || (await ctx.newPage());
await page.goto('https://yay.space/', { waitUntil: 'domcontentloaded' }).catch(() => {});
await page.waitForTimeout(2500);
const before = page.url();
// 「ログイン」ボタン
const btn = page.locator('button:has-text("ログイン")').first();
if (await btn.count()) { await btn.click().catch(() => {}); }
await page.waitForTimeout(3000);
console.log('URL after:', page.url(), '(before', before + ')');
// 露出した導線
const cands = await page.evaluate(() => {
  const out = [];
  for (const el of document.querySelectorAll('a,button,[role=button]')) {
    const t = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
    if (!t || t.length > 40) continue;
    if (/X|Twitter|続ける|continue|メール|email|ログイン|login|Google|Apple|電話/i.test(t)) {
      out.push({ tag: el.tagName, text: t, href: el.getAttribute('href') || '', cls: (el.className || '').toString().slice(0, 50) });
    }
  }
  return out.slice(0, 30);
});
console.log('導線:'); cands.forEach((c) => console.log('  ', JSON.stringify(c)));
await page.screenshot({ path: '/tmp/yay_login2.png' }).catch(() => {});
console.log('shot /tmp/yay_login2.png');
process.exit(0); // ★実Chromeを閉じない（disconnectのみ）
