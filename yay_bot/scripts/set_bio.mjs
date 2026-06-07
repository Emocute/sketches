// Yay の自己紹介(bio)を web セッション経由で設定する。
// edit_user API は web×モバイル署名の非互換で弾かれる(Invalid signed info)ため、
// ログイン済み profile-yay の web UI を Playwright で直接操作する。
//   編集モーダル: /user/<id>?modalMode=ue  /  bio: textarea[name=biography]  /  保存ボタン: text=保存
import { chromium } from 'playwright';
import { execFile } from 'child_process';
import { readFileSync } from 'fs';

const PROFILE = '/Users/emocute/.claude/playwright-profile-yay';
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = Number(process.env.BIO_PORT || 9243);
const CDP = `http://127.0.0.1:${PORT}`;
const UID = process.env.YAY_SELF_UID || '11320230';
const BIO = readFileSync(new URL('../social/bio.txt', import.meta.url).pathname, 'utf8').trim();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const up = async (u) => { try { return (await fetch(`${u}/json/version`)).ok; } catch { return false; } };

let proc;
if (!(await up(CDP))) {
  proc = execFile(CHROME, [`--user-data-dir=${PROFILE}`, `--remote-debugging-port=${PORT}`,
    '--remote-debugging-address=127.0.0.1', '--headless=new', '--no-first-run',
    '--no-default-browser-check', 'about:blank'], { detached: false });
  for (let i = 0; i < 30; i++) { if (await up(CDP)) break; await sleep(500); }
}

const browser = await chromium.connectOverCDP(CDP);
const ctx = browser.contexts()[0];
const page = await ctx.newPage();
try {
  await page.goto(`https://yay.space/user/${UID}?modalMode=ue`, { waitUntil: 'domcontentloaded' });
  const ta = page.locator('textarea[name="biography"]');
  await ta.waitFor({ state: 'visible', timeout: 15000 });
  // ★ モーダルは既存 bio を**遅延ロード**して React state に入れる。それより先に書き込むと
  //   後から来るロードに上書きされ旧値が保存される。ロード完了(非空)を待ってから上書きする。
  await page.waitForFunction(() => {
    const t = document.querySelector('textarea[name="biography"]');
    return t && t.value && t.value.length > 0;
  }, { timeout: 5000 }).catch(() => {});  // 元々 bio が空なら timeout で進む
  await sleep(700);
  const before = await ta.inputValue();
  // ★ React 制御 textarea にネイティブ setter + input イベントで一括投入（実キー入力は
  //   recaptcha 再描画でカーソルが飛び文字が混線する。pressSequentially 不可）。
  await ta.evaluate((el, val) => {
    const set = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    set.call(el, '');   el.dispatchEvent(new Event('input', { bubbles: true }));
    set.call(el, val);  el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }, BIO);
  await sleep(500);
  const after = await ta.inputValue();
  console.log(`bio before_len=${before.length} after_len=${after.length} (want ${BIO.length})`);

  // recaptcha v3(不可視)トークンの発行を待ってから保存（早すぎると空 token で無視される）
  await page.waitForFunction(() => {
    const r = document.querySelector('textarea.g-recaptcha-response');
    return r && r.value && r.value.length > 0;
  }, { timeout: 12000 }).catch(() => console.log('  (recaptcha token 待ちタイムアウト→そのまま保存試行)'));

  const save = page.getByRole('button', { name: '保存', exact: true }).first();
  const editResp = page.waitForResponse(
    (r) => r.url().includes('/v3/users/edit') && r.request().method() === 'POST',
    { timeout: 15000 }).catch(() => null);
  await save.click();
  const resp = await editResp;
  let body = '';
  if (resp) body = await resp.text().catch(() => '');
  await sleep(1500);
  // 成否判定は edit POST の success で行う（モーダル再オープンは bio を遅延ロードし空を返す
  // ことがあり当てにならない。真値はプロフィール表示 or get_user API）。
  const ok = !!resp && resp.status() === 200 && /success/.test(body);
  console.log(`edit POST status=${resp ? resp.status() : 'none'} body=${body.slice(0,60)}`);
  console.log(`RESULT ${ok ? 'OK（保存成功・真値は get_user で確認）' : 'FAIL'} typed_len=${after.length}`);
  process.exitCode = ok ? 0 : 1;
} catch (e) {
  console.error('set_bio failed:', e.message);
  process.exitCode = 2;
} finally {
  await page.close().catch(()=>{});
  await browser.close().catch(()=>{});
  if (proc) proc.kill();
}
