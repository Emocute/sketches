import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => process.exit(0), 12000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
await page.keyboard.press('Escape').catch(()=>{});
await page.waitForTimeout(400);
let st = await page.evaluate(() => document.querySelector('.ConferenceCallScreen__toolbar__item--mic-muted') ? 'muted' : (document.querySelector('.ConferenceCallScreen__toolbar__item--mic') ? 'unmuted' : '?'));
if (st === 'muted') { await page.evaluate(()=>document.querySelector('.ConferenceCallScreen__toolbar__item--mic-muted')?.click()); await page.waitForTimeout(600); st='unmuted(解除した)'; }
console.log('mic mute state:', st);
process.exit(0);
