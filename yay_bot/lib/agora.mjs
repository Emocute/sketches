// Agora トランスポート層（全面API移行）。
// 制御下の Playwright Chromium で agora_client.html を開き、Yay通話のAgoraチャンネルへ
// RTC(音楽publisher)+RTM(チャット)で直接参加する。BlackHole/実Chrome経路は廃止。
//
// 設計:
//  - ブラウザは Playwright 同梱 Chromium（実Chromeでない＝profile汚染なし・権限自由）。
//  - autoplay 制限を外し、mic 権限を付与（BufferSourceAudioTrackにはmicはいらないがWebRTC健全化）。
//  - 音源は file:// だと fetch がCORSで弾かれ得るので、127.0.0.1 のローカルHTTPで配信して渡す。
import { chromium } from 'playwright';
import http from 'node:http';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { extname, resolve as pathResolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HTML = fileURLToPath(new URL('../agora_client.html', import.meta.url));
const ROOT = fileURLToPath(new URL('..', import.meta.url));

const MIME = { '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.aac': 'audio/aac', '.ogg': 'audio/ogg', '.opus': 'audio/ogg', '.wav': 'audio/wav', '.flac': 'audio/flac' };

// ローカル音源を 127.0.0.1 で配信。?p=<絶対パス> をRange対応で返す（CORS全許可）。
export function startFileServer(port = 0) {
  return new Promise((resolveP) => {
    const server = http.createServer((req, res) => {
      try {
        const u = new URL(req.url, 'http://127.0.0.1');
        const p = u.searchParams.get('p');
        if (!p || !existsSync(p) || !statSync(p).isFile()) { res.writeHead(404); return res.end('no file'); }
        const size = statSync(p).size;
        const type = MIME[extname(p).toLowerCase()] || 'application/octet-stream';
        const range = req.headers.range;
        const head = { 'Content-Type': type, 'Access-Control-Allow-Origin': '*', 'Accept-Ranges': 'bytes' };
        if (range) {
          const m = /bytes=(\d+)-(\d*)/.exec(range);
          const start = Number(m[1]); const end = m[2] ? Number(m[2]) : size - 1;
          res.writeHead(206, { ...head, 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1 });
          createReadStream(p, { start, end }).pipe(res);
        } else {
          res.writeHead(200, { ...head, 'Content-Length': size });
          createReadStream(p).pipe(res);
        }
      } catch (e) { res.writeHead(500); res.end(String(e)); }
    });
    server.listen(port, '127.0.0.1', () => resolveP({ server, port: server.address().port }));
  });
}

export function fileUrl(base, absPath) { return `${base}/audio?p=${encodeURIComponent(pathResolve(absPath))}`; }

export async function launchAgora({ headless = true } = {}) {
  const browser = await chromium.launch({
    headless,
    args: [
      '--autoplay-policy=no-user-gesture-required',
      '--use-fake-ui-for-media-stream',     // 権限ダイアログ自動許可
      '--disable-features=IsolateOrigins,site-per-process',
    ],
  });
  const ctx = await browser.newContext({ permissions: ['microphone'] });
  const page = await ctx.newPage();
  page.on('console', (m) => { if (/\[yay\]/.test(m.text())) console.log('  (page)', m.text()); });
  page.on('pageerror', (e) => console.error('  (page error)', e.message));
  await page.goto('file://' + HTML, { waitUntil: 'load' });
  await page.waitForFunction(() => !!window.YayAgora, { timeout: 15000 });
  return { browser, ctx, page };
}

const ev = (page, fn, ...args) => page.evaluate(fn, ...args);
export const join = (page, creds) => ev(page, (c) => window.YayAgora.join(c), creds);
export const playUrl = (page, url, opts) => ev(page, ([u, o]) => window.YayAgora.playUrl(u, o), [url, opts || {}]);
export const stopMusic = (page) => ev(page, () => window.YayAgora.stopMusic());
export const pauseMusic = (page) => ev(page, () => window.YayAgora.pauseMusic());
export const resumeMusic = (page) => ev(page, () => window.YayAgora.resumeMusic());
export const sendChat = (page, text) => ev(page, (t) => window.YayAgora.sendChat(t), text);
export const drainInbox = (page) => ev(page, () => window.YayAgora.drainInbox());
export const status = (page) => ev(page, () => window.YayAgora.status());
export const tail = (page, n) => ev(page, (k) => window.YayAgora.tail(k), n);
export const leave = (page) => ev(page, () => window.YayAgora.leave());

// --- selftest: トークン無しで SDK ロード/ページAPI を検証 ---
if (process.argv[1] && process.argv[1].endsWith('agora.mjs') && process.argv[2] === 'selftest') {
  const { browser, page } = await launchAgora({ headless: process.env.HEADFUL ? false : true });
  const probe = await page.evaluate(() => ({
    rtc: typeof window.AgoraRTC !== 'undefined' && !!AgoraRTC.createClient,
    rtm: typeof window.AgoraRTM !== 'undefined',
    api: !!window.YayAgora && Object.keys(window.YayAgora),
    rtcVersion: (window.AgoraRTC && AgoraRTC.VERSION) || null,
  }));
  console.log('SELFTEST', JSON.stringify(probe, null, 2));
  const { server } = await startFileServer(0);
  console.log('fileServer ok port', server.address().port);
  server.close();
  await browser.close();
  process.exit(probe.rtc && probe.rtm && probe.api ? 0 : 1);
}
