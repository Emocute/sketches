// 単一プロセスで「ログイン窓を開く＋生かす＋ログイン検知＋トークン採取」を完結。
// 実Google Chrome二重起動はmacOSで不安定（究メインと競合・harness掃除で死ぬ）。
// Playwright同梱Chromiumを launchPersistentContext(headful) で起動し、このnodeプロセスが
// ブラウザを保持し続ける＝窓が消えない。自分のcookieを自分で読むのでKeychain復号問題も無い。
// 究は開いた窓で「ログイン→Xで続ける」を押すだけ。検知したらトークンを .yay_token へ。
import { chromium } from 'playwright';
import { writeFileSync, existsSync, copyFileSync, readFileSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const PROFILE = '/Users/emocute/.claude/playwright-profile-yay-pw'; // Chromiumネイティブ専用
const OUT = fileURLToPath(new URL('../.yay_token', import.meta.url));
const PY = fileURLToPath(new URL('../.venv/bin/python', import.meta.url));
const API = fileURLToPath(new URL('../yay_api.py', import.meta.url));
const DONE = '/tmp/yay_login_done.json';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const MAX_MIN = Number(process.env.AWAIT_MIN || 30);

const ctx = await chromium.launchPersistentContext(PROFILE, {
  headless: false,
  viewport: null,
  args: [
    '--no-first-run', '--no-default-browser-check',
    '--window-size=1100,860', '--window-position=80,60',
    '--remote-debugging-port=9224', '--remote-debugging-address=127.0.0.1',
  ],
});
const page = ctx.pages()[0] || (await ctx.newPage());
await page.goto('https://yay.space/', { waitUntil: 'domcontentloaded' }).catch(() => {});
await page.bringToFront().catch(() => {});
console.log('[login] 窓を開いた。究: ログイン→Xで続ける を押してください。');

const pyCheck = () => new Promise((res) => execFile(PY, [API, 'check'], { timeout: 30000 }, (e, so) => {
  const ls = (so || '').trim().split('\n').filter(Boolean); let j = null;
  for (let i = ls.length - 1; i >= 0; i--) { try { j = JSON.parse(ls[i]); break; } catch {} }
  res(j || { ok: false, error: 'check解析不可' });
}));

const deadline = Date.now() + MAX_MIN * 60000;
let done = false;
while (!done && Date.now() < deadline) {
  try {
    const ck = await ctx.cookies('https://yay.space');
    const tok = ck.find((c) => c.name === '_yay_web_access_token');
    if (tok && tok.value) {
      if (existsSync(OUT)) { const old = readFileSync(OUT, 'utf8').trim(); if (old && old !== tok.value) copyFileSync(OUT, OUT + '.prev'); }
      writeFileSync(OUT, decodeURIComponent(tok.value));
      console.log('[login] ✓ ログイン検知。.yay_token 更新 len=' + tok.value.length);
      const chk = await pyCheck();
      writeFileSync(DONE, JSON.stringify({ ...chk, at: new Date().toISOString() }));
      console.log('[login] check:', JSON.stringify(chk));
      done = true;
    }
  } catch (e) { console.log('[login] poll err', e.message); }
  if (!done) await sleep(4000);
}
if (!done) writeFileSync(DONE, JSON.stringify({ ok: false, error: 'timeout', at: new Date().toISOString() }));
console.log('[login] 終了。窓は開けたまま（究が閉じてOK）。');
// ブラウザは閉じない（究がそのまま通話に使うかも）。プロセスは生かして窓維持。
await sleep(MAX_MIN * 60000);
