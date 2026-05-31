import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 22000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
await page.keyboard.press('Escape').catch(()=>{});
await page.waitForTimeout(400);
await page.evaluate(()=>document.querySelector('.ConferenceCallScreen__sound_management')?.click());
await page.waitForTimeout(1300);
// 全 select の中身を確認
const before = await page.$$eval('select', els => els.map((s,i)=>({ i, sel: s.options[s.selectedIndex]?.textContent.trim(), opts:[...s.options].map(o=>o.textContent.trim()) })));
console.log('selects before:', JSON.stringify(before));
// BlackHole option を持つ select を Playwright selectOption で設定
const selects = await page.$$('select');
let done = null;
for (let i=0;i<selects.length;i++){
  const opts = await selects[i].$$eval('option', os=>os.map(o=>o.textContent.trim()));
  if (opts.some(o=>/BlackHole/.test(o))){
    await selects[i].selectOption({ label: opts.find(o=>/BlackHole/.test(o)) });
    done = i;
  }
}
await page.waitForTimeout(1000);
const after = await page.$$eval('select', els => els.map(s=>s.options[s.selectedIndex]?.textContent.trim()));
console.log('set select index:', done, '/ after:', JSON.stringify(after));
await page.keyboard.press('Escape').catch(()=>{});
await page.screenshot({ path: 'assets/_mic_final.png' });
process.exit(0);
