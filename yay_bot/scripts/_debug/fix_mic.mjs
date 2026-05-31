import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 22000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
await page.keyboard.press('Escape').catch(()=>{});
await page.waitForTimeout(400);
// サウンド設定を開いて BlackHole を選択
await page.evaluate(()=>document.querySelector('.ConferenceCallScreen__sound_management')?.click());
await page.waitForTimeout(1200);
const set = await page.evaluate(() => {
  for (const s of document.querySelectorAll('select')) {
    const bh = [...s.options].find(o => /BlackHole/.test(o.textContent));
    if (bh) {
      const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;
      setter.call(s, bh.value);
      s.dispatchEvent(new Event('input',{bubbles:true}));
      s.dispatchEvent(new Event('change',{bubbles:true}));
      return s.options[s.selectedIndex]?.textContent.trim();
    }
  }
  return null;
});
console.log('mic select →', set);
await page.waitForTimeout(800);
await page.keyboard.press('Escape').catch(()=>{});
await page.waitForTimeout(600);
// ミュート解除（--mic-muted を押す）
const micState = await page.evaluate(() => {
  const muted = document.querySelector('.ConferenceCallScreen__toolbar__item--mic-muted');
  if (muted) { muted.click(); return 'was-muted→clicked'; }
  return document.querySelector('.ConferenceCallScreen__toolbar__item--mic') ? 'already-unmuted' : 'no-mic-btn';
});
console.log('mic mute:', micState);
await page.waitForTimeout(800);
const finalState = await page.evaluate(() => [...document.querySelectorAll('[class*="toolbar__item--mic"]')].map(e=>e.className.match(/mic[a-z-]*/)?.[0]));
console.log('mic final:', JSON.stringify(finalState));
await page.screenshot({ path: 'assets/_mic_final.png' });
process.exit(0);
