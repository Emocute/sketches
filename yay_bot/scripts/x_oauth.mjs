// 開いてるログインモーダルの「Xで続ける」を押し、X OAuth を自動で通す。
// 対象は login_window.mjs が保持する安定窓（CDP 9224）。PWは認証ファイルから実行時読み。
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
const CDP = 'http://127.0.0.1:9224';
const CRED = '/Users/emocute/Downloads/Site/docs/auth/.credentials_2026-05-20.md';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const X_USER = process.env.YAY_X_USER || 'emocutesounds';
function readPw() {
  if (process.env.YAY_X_PASS) return process.env.YAY_X_PASS;
  try { const l = readFileSync(CRED, 'utf8').split('\n').find((x) => /emocutesounds/.test(x) && /パスワード|password/i.test(x)); const m = l && l.match(/`([^`]+)`/); if (m) return m[1]; } catch {}
  return null;
}
const X_PASS = readPw();
const tok = async (ctx) => (await ctx.cookies('https://yay.space')).find((c) => c.name === '_yay_web_access_token');

const b = await chromium.connectOverCDP(CDP);
const ctx = b.contexts()[0];
let page = ctx.pages().find((p) => /yay/.test(p.url())) || ctx.pages()[0];
await page.bringToFront().catch(() => {});

// 「Xで続ける」クリック（popup or 同タブ）
const popupP = page.waitForEvent('popup', { timeout: 5000 }).catch(() => null);
const xbtn = page.locator(':is(button,a):visible').filter({ hasText: /Xで続ける|X で続ける|𝕏/ }).first();
console.log('Xボタン count:', await xbtn.count());
if (await xbtn.count()) await xbtn.click().catch((e) => console.log('click', e.message));
let xp = (await popupP) || page;
await sleep(3500);
console.log('X stage url:', xp.url());
await xp.screenshot({ path: '/tmp/X3.png' }).catch(() => {});

const t0 = Date.now();
while (Date.now() - t0 < 90000) {
  if (await tok(ctx)) { console.log('✓ 戻ってトークン付与'); break; }
  const userIn = xp.locator('input[autocomplete="username"], input[name="text"]').first();
  const passIn = xp.locator('input[name="password"], input[autocomplete="current-password"]').first();
  const authBtn = xp.locator('input#allow, [data-testid="OAuth_Consent_Button"], button:has-text("Authorize"), button:has-text("連携アプリを認証"), button:has-text("アプリにアクセスを許可"), button:has-text("許可")').first();
  if (await authBtn.count() && await authBtn.isVisible().catch(() => false)) { console.log('→ 認証許可 click'); await authBtn.click().catch(() => {}); await sleep(3500); await xp.screenshot({ path: '/tmp/X5.png' }).catch(() => {}); continue; }
  if (await passIn.count() && await passIn.isVisible().catch(() => false)) {
    if (!X_PASS) { console.log('PW読めず中断'); break; }
    await passIn.fill(X_PASS).catch(() => {});
    const lg = xp.locator('[data-testid="LoginForm_Login_Button"], button:has-text("Log in"), div[role=button]:has-text("ログイン"), button:has-text("ログイン")').first();
    await lg.click().catch(() => {}); await sleep(4000); await xp.screenshot({ path: '/tmp/X4b.png' }).catch(() => {}); continue;
  }
  if (await userIn.count() && await userIn.isVisible().catch(() => false)) {
    await userIn.fill(X_USER).catch(() => {});
    const nx = xp.locator('button:has-text("Next"), div[role=button]:has-text("次へ"), div[role=button]:has-text("Next"), button:has-text("次へ")').first();
    await nx.click().catch(() => {}); await sleep(3000); await xp.screenshot({ path: '/tmp/X4a.png' }).catch(() => {}); continue;
  }
  const body = (await xp.evaluate(() => document.body?.innerText?.slice(0, 220) || '').catch(() => '')) || '';
  if (/認証コード|verification code|2-step|セキュリティ|電話番号|不審|locked|ロック|captcha|認証して/i.test(body)) { console.log('⚠ 人手要:', body.replace(/\n+/g, ' ').slice(0, 140)); break; }
  await sleep(2500);
}
await xp.screenshot({ path: '/tmp/X6.png' }).catch(() => {});
console.log('done. token=', !!(await tok(ctx)), 'url=', xp.url());
process.exit(0);
