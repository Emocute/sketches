// ☰メニュー → ログイン → X OAuth 導線まで辿って調べる（実Chrome、close無し）。
import { chromium } from 'playwright';
const b = await chromium.connectOverCDP('http://127.0.0.1:9222');
const ctx = b.contexts()[0];
let page = ctx.pages().find((p) => /yay\.space/.test(p.url())) || (await ctx.newPage());
await page.goto('https://yay.space/', { waitUntil: 'domcontentloaded' }).catch(() => {});
await page.waitForTimeout(2500);

const dump = async (tag) => {
  const cands = await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll('a,button,[role=button]')) {
      const t = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
      if (!t || t.length > 45) continue;
      if (/X|Twitter|続ける|continue|メール|email|ログイン|login|Google|Apple|電話|始め/i.test(t))
        out.push({ tag: el.tagName, text: t, href: el.getAttribute('href') || '', cls: (el.className || '').toString().slice(0, 45) });
    }
    return out.slice(0, 25);
  });
  console.log(`-- ${tag} (url=${page.url()}) --`);
  cands.forEach((c) => console.log('  ', JSON.stringify(c)));
};

// ① ハンバーガー: header 左上の最初の button
const burger = page.locator('header button, .Header button, [class*=menu] button, [class*=Menu] button, [class*=burger]').first();
if (await burger.count()) { await burger.click().catch(() => {}); await page.waitForTimeout(1500); }
await page.screenshot({ path: '/tmp/yay_m1.png' }).catch(() => {});
await dump('menu開後');

// ② ログイン
const login = page.locator('button:has-text("ログイン"), a:has-text("ログイン")').first();
if (await login.count()) { await login.click().catch(() => {}); await page.waitForTimeout(2500); }
await page.screenshot({ path: '/tmp/yay_m2.png' }).catch(() => {});
await dump('ログイン押後');

// X/Twitter 導線があれば href も拾う
const xinfo = await page.evaluate(() => {
  const els = [...document.querySelectorAll('a,button,[role=button]')].filter((el) => /X|Twitter|続ける|連携/i.test((el.innerText || '').trim()));
  return els.map((el) => ({ text: (el.innerText || '').trim().slice(0, 30), href: el.getAttribute('href') || '', cls: (el.className || '').toString().slice(0, 50) }));
});
console.log('X導線詳細:', JSON.stringify(xinfo));
console.log('shots: /tmp/yay_m1.png /tmp/yay_m2.png');
process.exit(0);
