import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => process.exit(0), 20000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
// 既存cable接続の送信を捕るフック（prototype.send をパッチ）
await page.evaluate(() => {
  if (window.__hooked) return;
  window.__hooked = true; window.__cablelog = [];
  const ps = WebSocket.prototype.send;
  WebSocket.prototype.send = function (d) {
    try { if (/cable\.yay/.test(this.url || '')) window.__cablelog.push('SENT ' + String(d).slice(0, 350)); } catch {}
    return ps.call(this, d);
  };
});
console.log('フック注入完了。テスト送信して send フレームを捕る');
// テスト送信（cable send を誘発）
await page.evaluate(() => document.querySelector('.ConferenceCallScreen__toolbar__item--chat')?.click());
await page.waitForTimeout(1200);
const ta = await page.$('textarea.CallChatReplyForm__form__input');
if (ta) { await ta.click(); await ta.fill('🎵'); await page.click('button.Button--icon-chat-send').catch(()=>{}); }
await page.waitForTimeout(2500);
const log = await page.evaluate(() => window.__cablelog || []);
console.log('=== cable SENT frames ===');
console.log(JSON.stringify(log, null, 1));
process.exit(0);
