// ☰(左上アイコン)→ログイン→ログイン画面 を辿って撮る。close無し。
import { chromium } from 'playwright';
const b = await chromium.connectOverCDP('http://127.0.0.1:9222');
const ctx = b.contexts()[0];
let page = ctx.pages().find((p) => /yay\.space/.test(p.url())) || (await ctx.newPage());
await page.goto('https://yay.space/', { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
await page.waitForTimeout(1500);
const vp = page.viewportSize();
console.log('viewport', JSON.stringify(vp));

// ヘッダーのアイコンボタン群を座標で把握
const icons = await page.evaluate(() => [...document.querySelectorAll('header button, header a, [class*=Header] button, [class*=header] button')].map((el) => {
  const r = el.getBoundingClientRect();
  return { cls: el.className.toString().slice(0, 40), x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), w: Math.round(r.width) };
}).filter((b) => b.w > 0));
console.log('header icons:', JSON.stringify(icons));

// 左上 ☰ をクリック（座標 fallback）
const burgerCls = icons.find((i) => i.x < 80 && i.y < 80);
if (burgerCls) await page.mouse.click(burgerCls.x, burgerCls.y);
else await page.mouse.click(24, 24);
await page.waitForTimeout(1500);
await page.screenshot({ path: '/tmp/D1.png' });

// drawer内の「ログイン」可視確認→クリック
const login = page.locator('button:has-text("ログイン"):visible, a:has-text("ログイン"):visible').first();
console.log('visible login count:', await login.count());
if (await login.count()) { await login.click().catch((e) => console.log('login click', e.message)); await page.waitForTimeout(3000); }
await page.screenshot({ path: '/tmp/D2.png' });
console.log('url:', page.url(), 'pages:', ctx.pages().length);

// ログイン画面の選択肢（X/Apple/Google/メール）
const opts = await page.evaluate(() => [...document.querySelectorAll('button,a,[role=button]')].filter((el) => {
  const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0;
}).map((el) => (el.innerText || el.getAttribute('aria-label') || '').trim()).filter((t) => t && t.length < 30 && /X|Twitter|Apple|Google|メール|電話|続ける|ログイン|始め/i.test(t)));
console.log('login options:', JSON.stringify([...new Set(opts)]));
process.exit(0);
