import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 18000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
// チャット最下部へスクロール
await page.evaluate(() => { const w = document.querySelector('.Messages__wrapper, .Messages, .CallChatWindow'); if (w) w.scrollTop = w.scrollHeight; });
await page.waitForTimeout(800);
const msgs = await page.evaluate(() => [...document.querySelectorAll('.Messages__item')].map(r => ({
  who: (r.querySelector('.Messages__item__img img')?.getAttribute('alt')||'').replace(/のカバー写真$/,''),
  t: r.querySelector('.Messages__item__span--text')?.textContent?.trim()||'',
  time: r.querySelector('.Messages__item__time')?.textContent?.trim()||''
})));
console.log('件数:', msgs.length);
console.log('最新5:', JSON.stringify(msgs.slice(-5)));
process.exit(0);
