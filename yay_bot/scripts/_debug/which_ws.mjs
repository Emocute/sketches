import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => process.exit(0), 16000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
await page.evaluate(() => {
  window.__wslog = [];
  const ps = WebSocket.prototype.send;
  WebSocket.prototype.send = function (d) {
    try { const host = (this.url||'').replace(/^wss?:\/\//,'').split('/')[0].slice(0,30); const len = (d&&d.length)||0; const txt = (typeof d==='string')?d.slice(0,60):'[binary '+len+']'; window.__wslog.push(host+' | '+txt); } catch {}
    return ps.call(this, d);
  };
});
// テスト送信
await page.evaluate(() => document.querySelector('.ConferenceCallScreen__toolbar__item--chat')?.click());
await page.waitForTimeout(1000);
const ta = await page.$('textarea.CallChatReplyForm__form__input');
if (ta){ await ta.click(); await ta.fill('にゃ'); await page.click('button.Button--icon-chat-send').catch(()=>{}); console.log('送信'); }
await page.waitForTimeout(3000);
const log = await page.evaluate(() => window.__wslog || []);
console.log('=== 送信直後の全 ws send（host | data）===');
log.slice(-15).forEach(l => console.log(l));
process.exit(0);
