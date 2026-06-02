// 究のログイン完了を検知して、トークン自動採取→疎通確認まで自走する watcher。
// ★重要: CDP接続は「1本だけ張って使い回す」。毎ループ connectOverCDP すると接続がリークし
//   Chrome を不安定化させて窓ごと殺す（既知の事故。2026-06-03修正）。close は呼ばない。
import { chromium } from 'playwright';
import { writeFileSync, existsSync, copyFileSync, readFileSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const CDP = 'http://127.0.0.1:9222';
const OUT = fileURLToPath(new URL('../.yay_token', import.meta.url));
const PY = fileURLToPath(new URL('../.venv/bin/python', import.meta.url));
const API = fileURLToPath(new URL('../yay_api.py', import.meta.url));
const DONE = '/tmp/yay_login_done.json';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const MAX_MIN = Number(process.env.AWAIT_MIN || 20);
const up = async () => { try { return (await fetch(`${CDP}/json/version`)).ok; } catch { return false; } };
const pyCheck = () => new Promise((res) => execFile(PY, [API, 'check'], { timeout: 30000 }, (e, so) => {
  const lines = (so || '').trim().split('\n').filter(Boolean);
  let j = null; for (let i = lines.length - 1; i >= 0; i--) { try { j = JSON.parse(lines[i]); break; } catch {} }
  res(j || { ok: false, error: 'check出力解析不可' });
}));

const deadline = Date.now() + MAX_MIN * 60000;
console.log(`[await] ログイン待機（最大${MAX_MIN}分、単一CDP接続）`);
let browser = null;
async function ensure() {
  if (browser && browser.isConnected()) return browser;
  for (let i = 0; i < 30 && !(await up()); i++) await sleep(2000);
  browser = await chromium.connectOverCDP(CDP);
  browser.on('disconnected', () => { browser = null; });
  return browser;
}

let done = false;
while (!done && Date.now() < deadline) {
  try {
    const b = await ensure();
    const ctx = b.contexts()[0];
    const ck = await ctx.cookies('https://yay.space');
    const tok = ck.find((c) => c.name === '_yay_web_access_token');
    if (tok && tok.value) {
      if (existsSync(OUT)) { const old = readFileSync(OUT, 'utf8').trim(); if (old && old !== tok.value) copyFileSync(OUT, OUT + '.prev'); }
      writeFileSync(OUT, decodeURIComponent(tok.value));
      console.log(`[await] ✓ ログイン検知。.yay_token 更新 len=${tok.value.length}`);
      const chk = await pyCheck();
      writeFileSync(DONE, JSON.stringify({ ...chk, at: new Date().toISOString() }));
      console.log('[await] check:', JSON.stringify(chk));
      done = true;
    }
  } catch (e) { console.log('[await] poll err', e.message); browser = null; }
  if (!done) await sleep(4000);
}
if (!done) { writeFileSync(DONE, JSON.stringify({ ok: false, error: 'timeout', at: new Date().toISOString() })); console.log('[await] タイムアウト'); }
process.exit(0);
