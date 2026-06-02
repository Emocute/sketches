// ログイン中の profile-yay(実Chrome) から Yay ウェブセッションの access token を吸い直す。
// 既存トークン流用の正道（新規 oauth ログイン＝新デバイス扱いを避ける）。
//
// なぜ実Chrome+CDPか:
//  - profile-yay は実 Google Chrome 運用。cookie は macOS Keychain 鍵で暗号化されており、
//    Playwright 同梱 Chromium では復号できず空になる（検証済）。
//  - 実 Chrome を debug port 付きで起動し CDP の Network.getCookies 経由で読むと、
//    ブラウザが復号した生値を返す。
//  - --headless=new でウィンドウを出さない（focus を奪わない）。Keychain は login 鍵が
//    セッション中 unlock 済なのでプロンプト無しで復号できる。
//  - yay.space を開くと、セッションが生きていれば access token が自動更新される。
import { chromium } from 'playwright';
import { writeFileSync, existsSync, copyFileSync, readFileSync } from 'fs';
import { execFile } from 'child_process';

const PROFILE = '/Users/emocute/.claude/playwright-profile-yay';
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const LIVE = 'http://127.0.0.1:9222';                 // 究のログイン窓（launch_yay.sh）
const PORT = Number(process.env.GRAB_PORT || 9242);   // ライブが無い時だけ headless で自前起動
const CDP = `http://127.0.0.1:${PORT}`;
const OUT = new URL('../.yay_token', import.meta.url).pathname;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const up = async (u) => { try { return (await fetch(`${u}/json/version`)).ok; } catch { return false; } };

// ① 究がログイン中の 9222 が生きてればそこから読む（同 profile の二重起動を避ける／最新 cookie）
// ② 無ければ自前で headless 起動して読む
let proc, endpoint;
if (await up(LIVE)) {
  endpoint = LIVE;
} else {
  endpoint = CDP;
  if (!(await up(CDP))) {
    proc = execFile(CHROME, [
      `--user-data-dir=${PROFILE}`,
      `--remote-debugging-port=${PORT}`,
      '--remote-debugging-address=127.0.0.1',
      '--headless=new',
      '--no-first-run', '--no-default-browser-check',
      'https://yay.space/',
    ], { detached: false });
    for (let i = 0; i < 40 && !(await up(CDP)); i++) await sleep(500);
  }
}

const browser = await chromium.connectOverCDP(endpoint);
try {
  // ページを開いてセッションのトークン自動更新を促す
  const ctx = browser.contexts()[0] || (await browser.newContext());
  let page = ctx.pages().find((p) => /yay\.space/.test(p.url()));
  if (!page) { page = await ctx.newPage(); await page.goto('https://yay.space/', { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {}); }
  await sleep(2500);

  const cookies = await ctx.cookies('https://yay.space');
  const tok = cookies.find((c) => c.name === '_yay_web_access_token');
  const uid = cookies.find((c) => c.name === '_yay_web_user_id');
  if (!tok || !tok.value) {
    console.error('[grab] _yay_web_access_token が空。cookies=', cookies.map((c) => c.name).join(','));
    process.exitCode = 2;
  } else {
    if (existsSync(OUT)) {
      const old = readFileSync(OUT, 'utf8').trim();
      if (old && old !== tok.value) copyFileSync(OUT, OUT + '.prev');
    }
    writeFileSync(OUT, decodeURIComponent(tok.value));
    const exp = tok.expires > 0 ? new Date(tok.expires * 1000).toISOString() : 'session';
    console.error(`[grab] .yay_token 更新: len=${tok.value.length} head=${tok.value.slice(0, 6)}… uid=${uid?.value || '?'} expires=${exp}`);
  }
} finally {
  // ★CDP接続の browser.close() は実Chrome本体を閉じてしまう。
  //   ライブ9222(究のログイン窓)に繋いだ時は絶対に閉じない＝disconnect のみ。
  if (proc && proc.pid) {
    await browser.close().catch(() => {});   // 自前 headless は閉じてよい
    try { process.kill(proc.pid); } catch {}
  }
  // ライブ接続時は close せず、プロセス終了で切断する（下の process.exit）
}
process.exit(process.exitCode || 0);
