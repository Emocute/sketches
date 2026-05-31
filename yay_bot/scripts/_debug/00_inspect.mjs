// Yay 調査スクリプト（読み取り専用・投稿しない）
// 用法: node scripts/00_inspect.mjs [chatURL]
//   引数なし → yay.space トップでログイン状態確認
//   chatURL あり → そのチャットを開いてメッセージ DOM 構造をダンプ
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';

const PROFILE = '/Users/emocute/.claude/playwright-profile-yay';
const __dir = path.dirname(fileURLToPath(import.meta.url));
const ASSETS = path.join(__dir, '..', 'assets');
const target = process.argv[2] || 'https://yay.space/';

const ctx = await chromium.launchPersistentContext(PROFILE, {
  channel: 'chrome',
  headless: false,
  viewport: null,
  args: ['--no-first-run', '--no-default-browser-check'],
});

const page = ctx.pages()[0] || (await ctx.newPage());
await page.goto(target, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(3500);

console.log('URL :', page.url());
console.log('Title:', await page.title());

// ログイン状態の推定（ログイン導線が残ってるか）
const loginHints = await page.evaluate(() => {
  const txt = document.body.innerText || '';
  const hasLoginWord = /ログイン|Log\s*in|Sign\s*in/i.test(txt);
  const hasLoginLink = !!document.querySelector('a[href*="login"]');
  return { hasLoginWord, hasLoginLink, bodyLen: txt.length };
});
console.log('login hints:', JSON.stringify(loginHints));

// チャットを開いてる場合: メッセージらしき要素の構造を推定ダンプ
if (process.argv[2]) {
  const probe = await page.evaluate(() => {
    // テキストを持つ末端要素のクラス頻度を集計（メッセージ行の候補を炙り出す）
    const freq = {};
    document.querySelectorAll('*').forEach((el) => {
      if (el.children.length === 0 && el.textContent && el.textContent.trim().length > 1) {
        const k = el.tagName.toLowerCase() + '.' + (el.className && el.className.toString ? el.className.toString().split(' ').slice(0, 2).join('.') : '');
        freq[k] = (freq[k] || 0) + 1;
      }
    });
    const top = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 25);
    // 入力欄候補
    const inputs = [...document.querySelectorAll('textarea, input[type="text"], [contenteditable="true"]')].map((el) => ({
      tag: el.tagName.toLowerCase(), type: el.type || null, ph: el.placeholder || null,
      ce: el.getAttribute('contenteditable'), cls: (el.className || '').toString().slice(0, 80),
    }));
    return { topTextNodeClasses: top, inputCandidates: inputs };
  });
  console.log('--- message-row class freq ---');
  console.log(JSON.stringify(probe.topTextNodeClasses, null, 0));
  console.log('--- input candidates ---');
  console.log(JSON.stringify(probe.inputCandidates, null, 2));
}

await page.screenshot({ path: path.join(ASSETS, '_debug_view.png'), fullPage: false });
console.log('screenshot -> assets/_debug_view.png');
console.log('（窓は開いたまま。確認したら手で閉じてOK。プロセスは残す）');
// 窓を残して観察できるように待機（Ctrl+C で終了）
await page.waitForTimeout(600000);
await ctx.close();
