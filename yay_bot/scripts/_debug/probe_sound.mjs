import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 22000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
await page.bringToFront().catch(()=>{});
// 開いてるモーダル(チャット等)を閉じる
await page.keyboard.press('Escape').catch(()=>{});
await page.waitForTimeout(600);
// チャットモーダルの×があれば閉じる
await page.evaluate(()=>{ const x=document.querySelector('.Modal__header .Modal__close, .Modal__close, [class*="close"]'); if(x) x.click(); }).catch(()=>{});
await page.waitForTimeout(600);
// sound_management を JS で直接クリック（actionability 待ちを回避）
const clicked = await page.evaluate(()=>{ const b=document.querySelector('.ConferenceCallScreen__sound_management'); if(b){ b.click(); return true;} return false; });
console.log('sound_management clicked:', clicked);
await page.waitForTimeout(1500);
const info = await page.evaluate(() => {
  const selects = [...document.querySelectorAll('select')].map(s => ({ cls:(s.className||'').slice(0,40), opts:[...s.options].map(o=>o.textContent.trim()) }));
  const labels = [...document.querySelectorAll('label,[class*="device"],[class*="Device"],[class*="mic"],[class*="Mic"],[class*="input"],[class*="Input"]')].map(e=>(e.textContent||'').trim()).filter(t=>t&&t.length<40).slice(0,20);
  const headers = [...document.querySelectorAll('[class*="Modal__header"] h2, h2, h3')].map(e=>e.textContent.trim()).slice(0,8);
  return { selects, labels:[...new Set(labels)], headers:[...new Set(headers)] };
});
console.log(JSON.stringify(info, null, 1));
await page.screenshot({ path: 'assets/_sound_settings.png' });
console.log('shot');
process.exit(0);
