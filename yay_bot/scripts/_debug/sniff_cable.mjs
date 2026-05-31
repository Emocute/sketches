import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { CONFIG } from '../config.mjs';
setTimeout(() => { console.log('--- 終了 ---'); process.exit(0); }, 22000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
page.on('websocket', (ws) => {
  if (!/cable\.yay\.space/.test(ws.url())) return;
  console.log('CABLE URL:', ws.url().slice(0, 60), '...(token保存)');
  const tk = (ws.url().match(/token=([^&]+)/) || [])[1];
  if (tk) writeFileSync('.yay_cable_token', decodeURIComponent(tk));
  ws.on('framesent', (f) => { const d=(f.payload||'').toString(); if(d.length>2) console.log('SENT:', d.slice(0,300)); });
  ws.on('framereceived', (f) => { const d=(f.payload||'').toString(); if(!/"type":"ping"/.test(d) && d.length>2) console.log('RECV:', d.slice(0,300)); });
});
console.log('リロード→cable傍受。途中でチャットに1つ送信して（送信フレームと受信フレーム両方捕る）');
await page.reload({ waitUntil: 'domcontentloaded' }).catch(()=>{});
await page.waitForTimeout(19000);
