import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => process.exit(0), 10000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
const st = await page.evaluate(() => ({
  mic: document.querySelector('.ConferenceCallScreen__toolbar__item--mic-muted') ? 'MUTED' : (document.querySelector('.ConferenceCallScreen__toolbar__item--mic') ? 'unmuted' : '?'),
}));
console.log('mic:', st.mic);
process.exit(0);
