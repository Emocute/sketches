// 通話の音声を「音楽が究/部屋に通る」状態にする（通話参加後に1回実行）。
//   1) Emo Claude の通話マイク入力 = BlackHole 2ch
//   2) マイクのミュート解除
// bot とは別接続。実行中だけ一瞬 9222 を触る（bot は止めなくてよいが、競合回避で止め推奨）。
import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';

setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 25000);
const browser = await chromium.connectOverCDP(CONFIG.cdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find((p) => /conference/.test(p.url())) || ctx.pages()[0];
if (!/conference/.test(page.url())) { console.log('通話画面ではない:', page.url()); process.exit(1); }

await page.keyboard.press('Escape').catch(() => {});
await page.waitForTimeout(400);
// 通話音声設定を開く → BlackHole を選択
await page.evaluate(() => document.querySelector('.ConferenceCallScreen__sound_management')?.click());
await page.waitForTimeout(1200);
const selects = await page.$$('select');
let set = null;
for (const s of selects) {
  const opts = await s.$$eval('option', (os) => os.map((o) => o.textContent.trim()));
  const bh = opts.find((o) => /BlackHole/.test(o));
  if (bh) { await s.selectOption({ label: bh }); set = bh; }
}
await page.waitForTimeout(800);
await page.keyboard.press('Escape').catch(() => {});
await page.waitForTimeout(500);
// ミュート解除
const micState = await page.evaluate(() => {
  const muted = document.querySelector('.ConferenceCallScreen__toolbar__item--mic-muted');
  if (muted) { muted.click(); return 'unmuted(解除した)'; }
  return document.querySelector('.ConferenceCallScreen__toolbar__item--mic') ? 'already-unmuted' : '?';
});
console.log('mic device →', set, '/ mute →', micState);
process.exit(0);
