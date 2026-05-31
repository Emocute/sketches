import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 22000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
await page.bringToFront().catch(()=>{});
await page.keyboard.press('Escape').catch(()=>{});
await page.waitForTimeout(500);
// サウンド設定を開く
await page.evaluate(()=>{ document.querySelector('.ConferenceCallScreen__sound_management')?.click(); });
await page.waitForTimeout(1200);
// BlackHole を含む option を持つ select を選ぶ
const result = await page.evaluate(() => {
  const selects = [...document.querySelectorAll('select')];
  const out = [];
  for (const s of selects) {
    const bh = [...s.options].find(o => /BlackHole/.test(o.textContent));
    if (bh) {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
      nativeSetter.call(s, bh.value);
      s.dispatchEvent(new Event('input', { bubbles: true }));
      s.dispatchEvent(new Event('change', { bubbles: true }));
      out.push({ set: bh.textContent.trim(), value: bh.value });
    } else {
      out.push({ skip: [...s.options].map(o=>o.textContent.trim()) });
    }
  }
  return out;
});
console.log('select result:', JSON.stringify(result));
await page.waitForTimeout(800);
// 現在の選択値を確認
const current = await page.evaluate(() => [...document.querySelectorAll('select')].map(s => s.options[s.selectedIndex]?.textContent.trim()));
console.log('current selected:', JSON.stringify(current));
await page.screenshot({ path: 'assets/_mic_set.png' });
process.exit(0);
