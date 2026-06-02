// profile-yay のログイン状態を診断（headless 実Chrome+CDP）。
import { chromium } from 'playwright';
import { execFile } from 'child_process';
const PROFILE = '/Users/emocute/.claude/playwright-profile-yay';
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = 9243, CDP = `http://127.0.0.1:${PORT}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const up = async () => { try { return (await fetch(`${CDP}/json/version`)).ok; } catch { return false; } };

let proc;
if (!(await up())) {
  proc = execFile(CHROME, [`--user-data-dir=${PROFILE}`, `--remote-debugging-port=${PORT}`, '--remote-debugging-address=127.0.0.1', '--headless=new', '--no-first-run', '--no-default-browser-check', 'https://yay.space/'], {});
  for (let i = 0; i < 40 && !(await up()); i++) await sleep(500);
}
const browser = await chromium.connectOverCDP(CDP);
try {
  const ctx = browser.contexts()[0];
  let page = ctx.pages().find((p) => /yay/.test(p.url())) || await ctx.newPage();
  await page.goto('https://yay.space/', { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
  await sleep(5000);
  const url = page.url();
  const title = await page.title().catch(() => '');
  const bodyText = (await page.evaluate(() => document.body?.innerText?.slice(0, 400) || '').catch(() => '')) || '';
  const hasLogin = /ログイン|login|sign\s*in|メールアドレス|パスワード/i.test(bodyText);
  const all = await ctx.cookies();
  const yayCk = all.filter((c) => /yay/.test(c.domain)).map((c) => c.name);
  const hasToken = yayCk.includes('_yay_web_access_token');
  console.error('URL:', url);
  console.error('TITLE:', title);
  console.error('login画面っぽい:', hasLogin);
  console.error('access_token cookie:', hasToken);
  console.error('yay cookies:', yayCk.join(','));
  console.error('--- body先頭 ---\n' + bodyText.replace(/\n{2,}/g, '\n'));
} finally {
  await browser.close().catch(() => {});
  if (proc?.pid) { try { process.kill(proc.pid); } catch {} }
}
