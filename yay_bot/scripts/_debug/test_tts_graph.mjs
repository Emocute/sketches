// playTTS の WebAudio グラフが「音を運ぶ」かを headless で実測する診断。
// agora_client.html と同じグラフ(createMediaElementSource→ttsGain→MediaStreamDestination)を組み、
// 本物のずんだもん WAV を流して、出力 track 側の RMS を AnalyserNode で測る。
// RMS>0 = グラフ正常（=不具合は speaking トグル側）。RMS≈0 = グラフに bug。
import { chromium } from 'playwright';
import http from 'node:http';
import { createReadStream, statSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));
// 最新の TTS WAV を1つ用意（無ければ生成）
let wav = execFileSync('bash', ['-lc', `ls -t ${HERE}/../../_tts_tmp/*.wav 2>/dev/null | head -1`]).toString().trim();
if (!wav || !existsSync(wav)) { console.error('WAV が無い。先に tts.speak を回して'); process.exit(1); }
console.log('テスト WAV:', wav, statSync(wav).size, 'bytes');

// ACAO:* で WAV を配る簡易サーバ（本番 file server と同じヘッダ条件）
const srv = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'audio/wav', 'Access-Control-Allow-Origin': '*', 'Content-Length': statSync(wav).size });
  createReadStream(wav).pipe(res);
});
await new Promise((r) => srv.listen(0, '127.0.0.1', r));
const url = `http://127.0.0.1:${srv.address().port}/a.wav`;

const browser = await chromium.launch({ headless: true, args: ['--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage();
page.on('console', (m) => console.log('  (page)', m.text()));
page.on('pageerror', (e) => console.error('  (page err)', e.message));
await page.goto('about:blank');

const rms = await page.evaluate(async (u) => {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === 'suspended') await ctx.resume();
  const dest = ctx.createMediaStreamDestination();
  const ttsGain = ctx.createGain(); ttsGain.gain.value = 0.3;   // 本番 S.ttsVol=30 相当
  ttsGain.connect(dest);
  // 出力 track 側を解析（= Agora に publish される音そのもの）
  const probe = ctx.createMediaStreamSource(dest.stream);
  const an = ctx.createAnalyser(); an.fftSize = 2048; probe.connect(an);

  const a = new Audio(); a.crossOrigin = 'anonymous'; a.src = u;
  await new Promise((res, rej) => {
    const ok = () => res(); const ng = () => rej(new Error('canplay失敗'));
    a.addEventListener('canplay', ok, { once: true });
    a.addEventListener('error', ng, { once: true });
    setTimeout(ok, 5000);
  });
  const node = ctx.createMediaElementSource(a);
  node.connect(ttsGain);
  await a.play();

  // 2秒間 RMS をサンプリングして最大値を返す
  const buf = new Float32Array(an.fftSize);
  let peak = 0;
  for (let i = 0; i < 20; i++) {
    await new Promise((r) => setTimeout(r, 100));
    an.getFloatTimeDomainData(buf);
    let s = 0; for (const v of buf) s += v * v;
    const r = Math.sqrt(s / buf.length);
    if (r > peak) peak = r;
  }
  return { peak, ctxState: ctx.state, paused: a.paused, dur: a.duration };
}, url);

console.log('RESULT:', JSON.stringify(rms));
console.log(rms.peak > 0.001 ? '✅ グラフは音を運んでいる（不具合は speaking トグル側）' : '❌ グラフが無音（WebAudio 経路に bug）');
await browser.close();
srv.close();
