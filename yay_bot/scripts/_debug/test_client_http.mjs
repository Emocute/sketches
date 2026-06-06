// 本番 startFileServer + launchAgora(pageUrl) で client が http 配信から起動できるか検証。
// 1) window.YayAgora が ready（SDK が /node_modules/ から配信され読めた）
// 2) 音源 wav を http から fetch して decodeAudioData できる（PNA で死なない）
import * as agora from '../../lib/agora.mjs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const HERE = fileURLToPath(new URL('.', import.meta.url));
const wav = execFileSync('bash', ['-lc', `ls -t ${HERE}/../../_tts_tmp/*.wav 2>/dev/null | head -1`]).toString().trim();

const fs = await agora.startFileServer(0);
const base = `http://127.0.0.1:${fs.port}`;
console.log('file server', base);
const a = await agora.launchAgora({ headless: true, pageUrl: `${base}/client` });
console.log('window.YayAgora ready =', await a.page.evaluate(() => !!window.YayAgora));
const r = await a.page.evaluate(async (u) => {
  try {
    const resp = await fetch(u); const buf = await resp.arrayBuffer();
    const ctx = new AudioContext(); const ab = await ctx.decodeAudioData(buf);
    return { ok: true, bytes: buf.byteLength, durSec: +ab.duration.toFixed(2) };
  } catch (e) { return { ok: false, err: String(e) }; }
}, agora.fileUrl(base, wav));
console.log('音源 http fetch+decode:', JSON.stringify(r));
console.log(r.ok ? '✅ client http起動OK・音源も読める（PNA回避成功）' : '❌ まだ読めない');
await a.browser.close(); fs.server.close();
