// Yay へ X OAuth で自動ログインし、トークンを採取する（究: お前がやれ）。
// 単一CDP接続・close無し・各段スクショ。X PW は gitignore 済み認証ファイルから実行時に読む
// （コマンドライン/標準出力にPWを出さない）。2FA/captcha が出たら停止して報告。
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync, copyFileSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const CDP = 'http://127.0.0.1:9222';
const OUT = fileURLToPath(new URL('../.yay_token', import.meta.url));
const PY = fileURLToPath(new URL('../.venv/bin/python', import.meta.url));
const API = fileURLToPath(new URL('../yay_api.py', import.meta.url));
const CRED = '/Users/emocute/Downloads/Site/docs/auth/.credentials_2026-05-20.md';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const shot = (page, n) => page.screenshot({ path: `/tmp/X${n}.png` }).catch(() => {});

// 認証情報（PWは出力しない）
const X_USER = process.env.YAY_X_USER || 'emocutesounds';
function readPw() {
  if (process.env.YAY_X_PASS) return process.env.YAY_X_PASS;
  try {
    const line = readFileSync(CRED, 'utf8').split('\n').find((l) => /emocutesounds/.test(l) && /パスワード|password/i.test(l));
    const m = line && line.match(/`([^`]+)`/);
    if (m) return m[1];
  } catch {}
  return null;
}
const X_PASS = readPw();

const cookieTok = async (ctx) => (await ctx.cookies('https://yay.space')).find((c) => c.name === '_yay_web_access_token');

async function harvest(ctx) {
  const tok = await cookieTok(ctx);
  if (!tok || !tok.value) return false;
  if (existsSync(OUT)) { const old = readFileSync(OUT, 'utf8').trim(); if (old && old !== tok.value) copyFileSync(OUT, OUT + '.prev'); }
  writeFileSync(OUT, decodeURIComponent(tok.value));
  console.log('✓ token採取 len=' + tok.value.length);
  return true;
}
const pyCheck = () => new Promise((res) => execFile(PY, [API, 'check'], { timeout: 30000 }, (e, so) => {
  const ls = (so || '').trim().split('\n').filter(Boolean); let j = null;
  for (let i = ls.length - 1; i >= 0; i--) { try { j = JSON.parse(ls[i]); break; } catch {} }
  res(j || { ok: false });
}));

const b = await chromium.connectOverCDP(CDP);
const ctx = b.contexts()[0];
let page = ctx.pages().find((p) => /yay\.space/.test(p.url())) || (await ctx.newPage());

// 既にログイン済みなら即採取
await page.goto('https://yay.space/', { waitUntil: 'domcontentloaded' }).catch(() => {});
await page.waitForTimeout(2000);
if (await cookieTok(ctx)) { console.log('既にログイン済'); await harvest(ctx); console.log('check', JSON.stringify(await pyCheck())); process.exit(0); }

// ① ☰ ドロワーを開く（左上アイコン）
await shot(page, '0');
const header = await page.evaluate(() => {
  const el = document.querySelector('header button, [class*=Header] button, [class*=header] button');
  if (!el) return null; const r = el.getBoundingClientRect(); return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
});
await page.mouse.click(header?.x || 24, header?.y || 24);
await page.waitForTimeout(1200);
await shot(page, '1');

// ② ログイン
const login = page.locator(':is(button,a):has-text("ログイン"):visible').first();
if (await login.count()) { await login.click().catch((e) => console.log('login click', e.message)); }
await page.waitForTimeout(2500);
await shot(page, '2');
console.log('after-login url:', page.url());

// ③ X で続ける（同タブ遷移 or popup）
let xpage = page;
const popupP = page.waitForEvent('popup', { timeout: 4000 }).catch(() => null);
const xbtn = page.locator(':is(button,a):visible').filter({ hasText: /Xで|X で|Twitter|𝕏|Xで続ける/ }).first();
if (await xbtn.count()) { await xbtn.click().catch((e) => console.log('xbtn click', e.message)); }
else {
  // テキスト無しのXロゴボタンの可能性 → aria-label/クラスで探す
  const alt = page.locator('[aria-label*="X"],[class*=twitter i],[class*=Twitter],[class*=sns] button').first();
  if (await alt.count()) await alt.click().catch(() => {});
}
const popup = await popupP;
if (popup) { xpage = popup; console.log('popup:', await xpage.url().catch(() => '?')); }
await sleep(3500);
await shot(xpage, '3');
console.log('x-stage url:', xpage.url());

// ④ X 側を処理（ログインフォーム / 認証ボタン）を最大90秒ループ
const t0 = Date.now();
while (Date.now() - t0 < 90000) {
  if (await cookieTok(ctx)) break; // 戻ってトークン付与された
  const u = xpage.url();
  // username 入力
  const userIn = xpage.locator('input[autocomplete="username"], input[name="text"]').first();
  const passIn = xpage.locator('input[name="password"], input[autocomplete="current-password"]').first();
  const authBtn = xpage.locator('input#allow, [data-testid="OAuth_Consent_Button"], button:has-text("Authorize"), button:has-text("連携アプリを認証"), button:has-text("アプリにアクセスを許可")').first();
  if (await authBtn.count()) { console.log('→ 認証ボタン click'); await authBtn.click().catch(() => {}); await sleep(3000); await shot(xpage, '5'); continue; }
  if (await passIn.count() && await passIn.isVisible().catch(() => false)) {
    if (!X_PASS) { console.log('PW未取得（認証ファイルから読めず）。中断。'); break; }
    await passIn.fill(X_PASS).catch(() => {});
    const lg = xpage.locator('[data-testid="LoginForm_Login_Button"], button:has-text("Log in"), button:has-text("ログイン"), div[role=button]:has-text("ログイン")').first();
    await lg.click().catch(() => {}); await sleep(4000); await shot(xpage, '4b'); continue;
  }
  if (await userIn.count() && await userIn.isVisible().catch(() => false)) {
    await userIn.fill(X_USER).catch(() => {});
    const nx = xpage.locator('button:has-text("Next"), button:has-text("次へ"), div[role=button]:has-text("次へ"), div[role=button]:has-text("Next")').first();
    await nx.click().catch(() => {}); await sleep(3000); await shot(xpage, '4a'); continue;
  }
  // それ以外（2FA/認証コード/captcha 等）→ 人手
  const body = (await xpage.evaluate(() => document.body?.innerText?.slice(0, 200) || '').catch(() => '')) || '';
  if (/認証コード|verification code|2-step|セキュリティ|電話番号|confirm|不審|locked|ロック/i.test(body)) {
    console.log('⚠ 人手が必要そう:', body.replace(/\n+/g, ' ').slice(0, 120));
    break;
  }
  await sleep(2500);
}

await shot(xpage, '6');
const got = await harvest(ctx);
if (got) console.log('check', JSON.stringify(await pyCheck()));
else console.log('✗ トークン未採取。url=' + xpage.url() + ' /tmp/X*.png を確認。');
process.exit(0);
