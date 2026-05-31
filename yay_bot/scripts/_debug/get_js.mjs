import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => process.exit(0), 12000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
const srcs = await page.evaluate(() => [...document.querySelectorAll('script[src]')].map(s => s.src).filter(s => /\.js/.test(s)));
console.log(srcs.join('\n'));
process.exit(0);
