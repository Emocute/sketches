import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => { console.log('--- 終了 ---'); process.exit(0); }, 20000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
let rc = 0, sc = 0;
page.on('websocket', (ws) => {
  console.log('WS-OPEN:', ws.url().slice(0, 120));
  ws.on('framereceived', (f) => { if (rc++ < 6) { const d=(f.payload||'').toString(); console.log('  recv:', d.slice(0,160)); } });
  ws.on('framesent', (f) => { if (sc++ < 6) { const d=(f.payload||'').toString(); console.log('  sent:', d.slice(0,160)); } });
});
console.log('リロードして ws を捕捉...');
await page.reload({ waitUntil: 'domcontentloaded' }).catch(e=>console.log('reload:', e.message));
await page.waitForTimeout(16000);
