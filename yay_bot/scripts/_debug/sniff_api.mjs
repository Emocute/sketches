import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => { console.log('--- 終了 ---'); process.exit(0); }, 22000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /conference/.test(p.url())) || ctx.pages()[0];
const seen = new Set();
page.on('request', (req) => {
  const u = req.url(); if (!/api\.yay\.space/.test(u)) return;
  const path = u.replace('https://api.yay.space', '');
  const key = req.method() + ' ' + path.split('?')[0];
  if (seen.has(key)) return; seen.add(key);
  let body = ''; try { body = req.postData()?.slice(0,150) || ''; } catch {}
  console.log('API', req.method(), path.slice(0,100), body ? '| body:'+body : '');
});
page.on('websocket', (ws) => { console.log('WS', ws.url().slice(0,80)); ws.on('framesent', f=>{const d=(f.payload||'').toString();if(/text|message|chat/i.test(d))console.log('WSsent',d.slice(0,120));}); });

// チャットを閉じて→開く（履歴fetchを誘発）
await page.keyboard.press('Escape').catch(()=>{});
await page.waitForTimeout(800);
await page.evaluate(()=>document.querySelector('.ConferenceCallScreen__toolbar__item--chat')?.click());
await page.waitForTimeout(2500);
// テスト送信1回（send APIを誘発）
const ta = await page.$('textarea.CallChatReplyForm__form__input');
if (ta) { await ta.click(); await ta.fill('🎧'); await page.click('button.Button--icon-chat-send').catch(()=>{}); console.log('→ テスト送信した'); }
await page.waitForTimeout(3000);
