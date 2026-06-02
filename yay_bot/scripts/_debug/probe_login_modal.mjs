// ログインを押して出る画面を実際に撮る。クリック前後・ハンバーガーも。close無し。
import { chromium } from 'playwright';
const b = await chromium.connectOverCDP('http://127.0.0.1:9222');
const ctx = b.contexts()[0];
let page = ctx.pages().find((p) => /yay\.space/.test(p.url())) || (await ctx.newPage());
await page.goto('https://yay.space/', { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
await page.waitForTimeout(2000);
await page.screenshot({ path: '/tmp/L0.png' });

// 全buttonの可視情報を列挙（座標つき）
const btns = await page.evaluate(() => [...document.querySelectorAll('button,a,[role=button]')].map((el) => {
  const r = el.getBoundingClientRect();
  return { t: (el.innerText || '').trim().slice(0, 24), x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), w: Math.round(r.width), vis: r.width > 0 && r.height > 0 };
}).filter((b) => b.t && b.vis).slice(0, 40));
console.log('VISIBLE:', JSON.stringify(btns));

// ログインを実クリック
const login = page.locator('button:has-text("ログイン")').first();
console.log('login count:', await login.count());
if (await login.count()) {
  await login.scrollIntoViewIfNeeded().catch(() => {});
  await login.click({ timeout: 4000 }).catch((e) => console.log('click err', e.message));
}
await page.waitForTimeout(3000);
await page.screenshot({ path: '/tmp/L1.png' });
console.log('after url:', page.url(), 'pages:', ctx.pages().length);
// モーダル/ダイアログ要素
const modal = await page.evaluate(() => {
  const m = document.querySelector('[class*=odal],[class*=ialog],[role=dialog],[class*=Login],[class*=login]');
  return m ? { cls: m.className.toString().slice(0, 60), text: (m.innerText || '').slice(0, 200) } : null;
});
console.log('modal:', JSON.stringify(modal));
process.exit(0);
