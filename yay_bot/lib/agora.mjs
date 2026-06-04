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

// ローカル音源を 127.0.0.1 で配信。
//   /audio?p=<絶対パス>  … ローカルファイルを Range 対応で返す
//   /stream?u=<remoteURL> … 遠隔URL(googlevideo等)を pipe で中継（ディスク保存なし＝real-time）。
//                            captureStream を tainted にしないため CORS を付ける。
export function startFileServer(port = 0) {
  return new Promise((resolveP) => {
    const server = http.createServer(async (req, res) => {
      try {
        const u = new URL(req.url, 'http://127.0.0.1');
        // --- 遠隔URLストリーム中継（real-time、全DLしない） ---
        if (u.pathname === '/stream') {
          const remote = u.searchParams.get('u');
          if (!remote) { res.writeHead(400); return res.end('no u'); }
          const fwd = {};
          if (req.headers.range) fwd['Range'] = req.headers.range;
          // googlevideo は素直な UA を好む
          fwd['User-Agent'] = 'Mozilla/5.0';
          const up = await fetch(remote, { headers: fwd });
          const h = {
            'Content-Type': up.headers.get('content-type') || 'audio/mp4',
            'Access-Control-Allow-Origin': '*',
            'Accept-Ranges': 'bytes',
          };
          const clen = up.headers.get('content-length'); if (clen) h['Content-Length'] = clen;
          const crange = up.headers.get('content-range'); if (crange) h['Content-Range'] = crange;
          res.writeHead(up.status, h);
          if (!up.body) return res.end();
          const reader = up.body.getReader();
          for (;;) { const { done, value } = await reader.read(); if (done) break; res.write(Buffer.from(value)); }
          return res.end();
        }
        // --- ローカルファイル配信 ---
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
export function streamUrl(base, remoteUrl) { return `${base}/stream?u=${encodeURIComponent(remoteUrl)}`; }

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
export const playLive = (page, match) => ev(page, (m) => window.YayAgora.playLive(m), match || null);
// 読み上げ: TTS WAV(ローカルproxy)を ttsGain に乗せて喋らせる。音楽は止めずダッキング。
export const playTTS = (page, url) => ev(page, (u) => window.YayAgora.playTTS(u), url);
export const setMusicVolume = (page, v) => ev(page, (n) => window.YayAgora.setMusicVolume(n), v);
export const setLoop = (page, on) => ev(page, (o) => window.YayAgora.setLoop(o), on);
export const listAudioInputs = (page) => ev(page, () => window.YayAgora.listAudioInputs());
export const stopMusic = (page) => ev(page, () => window.YayAgora.stopMusic());
export const pauseMusic = (page) => ev(page, () => window.YayAgora.pauseMusic());
export const resumeMusic = (page) => ev(page, () => window.YayAgora.resumeMusic());
export const sendChat = (page, text) => ev(page, (t) => window.YayAgora.sendChat(t), text);
export const drainInbox = (page) => ev(page, () => window.YayAgora.drainInbox());
export const status = (page) => ev(page, () => window.YayAgora.status());
export const tail = (page, n) => ev(page, (k) => window.YayAgora.tail(k), n);
export const leave = (page) => ev(page, () => window.YayAgora.leave());
// 聞き取り（通話音声の文字起こし用）
export const startListen = (page, opts) => ev(page, (o) => window.YayAgora.startListen(o), opts || {});
export const stopListen = (page) => ev(page, () => window.YayAgora.stopListen());
export const drainUtterances = (page) => ev(page, () => window.YayAgora.drainUtterances());
export const listenStatus = (page) => ev(page, () => window.YayAgora.listenStatus());

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
