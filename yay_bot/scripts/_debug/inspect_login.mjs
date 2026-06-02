// Yay ログインUIを調査（実Chrome 9222 にCDP接続、読み取り中心）。
import { chromium } from 'playwright';
const b = await chromium.connectOverCDP('http://127.0.0.1:9222');
const ctx = b.contexts()[0];
let page = ctx.pages().find((p) => /yay\.space/.test(p.url())) || (await ctx.newPage());
await page.goto('https://yay.space/', { waitUntil: 'domcontentloaded' }).catch(() => {});
await page.waitForTimeout(3500);
console.log('URL:', page.url());
console.log('TITLE:', await page.title().catch(() => ''));
// ログイン状態の手掛かり
const ck = await ctx.cookies('https://yay.space');
console.log('access_token cookie:', ck.some((c) => c.name === '_yay_web_access_token'));
// クリック可能なログイン導線テキストを収集
const cands = await page.evaluate(() => {
  const out = [];
  for (const el of document.querySelectorAll('a,button,[role=button],div[class*=ogin],div[class*=login]')) {
    const t = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
    if (!t) continue;
    if (/ログイン|login|始める|はじめる|X|Twitter|続ける|continue|sign/i.test(t) && t.length < 40) {
      out.push({ tag: el.tagName, text: t, href: el.getAttribute('href') || '', cls: (el.className || '').toString().slice(0, 60) });
    }
  }
  return out.slice(0, 30);
});
console.log('LOGIN候補:'); cands.forEach((c) => console.log('  ', JSON.stringify(c)));
await page.screenshot({ path: '/tmp/yay_login.png', fullPage: false }).catch(() => {});
console.log('screenshot: /tmp/yay_login.png');
await b.close();
