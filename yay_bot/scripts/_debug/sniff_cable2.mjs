import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => { console.log('--- 終了 ---'); process.exit(0); }, 24000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
const client = await ctx.newCDPSession(page);
await client.send('Network.enable');
const cable = {};
client.on('Network.webSocketCreated', (e) => { if (/cable\.yay/.test(e.url)) { cable[e.requestId] = 1; console.log('CABLE created'); } });
client.on('Network.webSocketFrameSent', (e) => { if (cable[e.requestId]) { const d=e.response.payloadData; if(d.length>2) console.log('SENT:', d.slice(0,400)); } });
client.on('Network.webSocketFrameReceived', (e) => { if (cable[e.requestId]) { const d=e.response.payloadData; if(d.length>2 && !/"type":"ping"/.test(d)) console.log('RECV:', d.slice(0,400)); } });
console.log('reload→cable全フレーム捕捉');
await page.reload({ waitUntil: 'domcontentloaded' }).catch(()=>{});
await page.waitForTimeout(6000);
// チャット開いてテスト送信（送信フレーム＋エコー受信を捕る）
await page.evaluate(()=>document.querySelector('.ConferenceCallScreen__toolbar__item--chat')?.click());
await page.waitForTimeout(1500);
const ta = await page.$('textarea.CallChatReplyForm__form__input');
if (ta){ await ta.click(); await ta.fill('test'); await page.click('button.Button--icon-chat-send').catch(()=>{}); console.log('→ test送信'); }
await page.waitForTimeout(8000);
