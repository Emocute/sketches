// 音楽が通話に流れるまでの全リンクを ✓/✗ で点検する（通話参加中に叩く）。
//   実行: node scripts/diag_audio.mjs
// 経路: Vivaldi(音楽) --setSinkId--> BlackHole --> Yay通話マイク入力 --> 部屋/究
import { chromium } from 'playwright';
import { execSync } from 'child_process';
import { CONFIG } from '../config.mjs';

const ok = (b) => (b ? '✓' : '✗');
const line = (b, label, detail = '') => console.log(`  ${ok(b)} ${label}${detail ? ' — ' + detail : ''}`);
setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 30000);

console.log('\n== yay_bot 音声経路 診断 ==\n');

// 0) OS に BlackHole があるか
let bhOS = false;
try { bhOS = /BlackHole 2ch/.test(execSync('system_profiler SPAudioDataType', { encoding: 'utf8' })); } catch {}
line(bhOS, 'OS: BlackHole 2ch が存在', bhOS ? '' : 'brew install --cask blackhole-2ch');

// 1) 音楽ブラウザ Vivaldi(9223)
console.log('\n[ 音楽ブラウザ Vivaldi ]');
let mediaState = null, sinkLabel = null;
try {
  const mb = await chromium.connectOverCDP(CONFIG.musicCdpUrl);
  for (const c of mb.contexts()) { try { await c.grantPermissions(['microphone']); } catch {} } // ラベル露出（fake-ui フラグ代替）
  const allPages = mb.contexts().flatMap((c) => c.pages());
  const mp = allPages.find((p) => /youtube|spotify/.test(p.url())) || allPages[0];
  if (!mp) { line(false, 'CDP 9223 接続', 'タブが無い → music ブラウザでタブを1つ開いて'); throw new Error('no page'); }
  line(true, 'CDP 9223 接続', mp.url().slice(0, 60));
  const r = await mp.evaluate(async (prefer) => {
    if (!navigator.mediaDevices) return { blank: true, url: location.href };
    try { const s = await navigator.mediaDevices.getUserMedia({ audio: true }); s.getTracks().forEach((t) => t.stop()); } catch {}
    const outs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'audiooutput');
    let dev = null; for (const m of prefer) { dev = outs.find((d) => new RegExp(m, 'i').test(d.label)); if (dev) break; }
    const els = [...document.querySelectorAll('audio,video')];
    return {
      labels: outs.map((d) => d.label),
      target: dev?.label || null,
      media: els.map((el) => ({ sink: el.sinkId || 'default', onTarget: dev ? el.sinkId === dev.deviceId : false, paused: el.paused, muted: el.muted, vol: el.volume, t: Math.round(el.currentTime * 10) / 10 })),
    };
  }, CONFIG.sinkPrefer);
  if (r.blank) { line(false, '音楽ページが待機中(about:blank)', '/play すれば YouTube に遷移して経路が貼られる'); }
  else {
  sinkLabel = r.target;
  line(!!r.target, '出力デバイス候補あり', r.target || ('候補なし / 一覧: ' + r.labels.join(', ')));
  const routed = r.media.filter((m) => m.onTarget);
  const playing = r.media.filter((m) => !m.paused && !m.muted && m.vol > 0 && m.t > 0);
  line(r.media.length > 0, '再生要素(audio/video)あり', r.media.length + '個');
  line(routed.length > 0, 'setSinkId が出力先に適用済', routed.length + '/' + r.media.length + '要素');
  line(playing.length > 0, '実際に再生が進んでる', playing.length ? 'currentTime進行中' : '停止/無音/未選曲');
  mediaState = r;
  }
} catch (e) { line(false, 'CDP 9223 接続', e.message + ' → scripts/launch_music.sh'); }

// 2) Yay 通話ブラウザ(9222)
console.log('\n[ Yay 通話ブラウザ ]');
try {
  const yb = await chromium.connectOverCDP(CONFIG.cdpUrl);
  const yPages = yb.contexts().flatMap((c) => c.pages());
  const yp = yPages.find((p) => /conference/.test(p.url())) || yPages.find((p) => /yay\.space/.test(p.url())) || yPages[0];
  if (!yp) { line(false, 'CDP 9222 接続', 'タブが無い'); throw new Error('no page'); }
  line(true, 'CDP 9222 接続', yp.url().slice(0, 60));
  const inCall = /conference/.test(yp.url());
  line(inCall, '通話画面 /conference に居る', inCall ? '' : '通話に参加して');
  if (inCall) {
    await yp.evaluate(() => document.querySelector('.ConferenceCallScreen__sound_management')?.click());
    await yp.waitForTimeout(900);
    const mic = await yp.evaluate(() => {
      const sels = [...document.querySelectorAll('select')];
      for (const s of sels) { const o = [...s.options].find((x) => /BlackHole/i.test(x.textContent)); if (o) return { has: true, selected: s.value === o.value, label: o.textContent.trim() }; }
      return { has: false };
    });
    await yp.keyboard.press('Escape').catch(() => {});
    line(mic.has, '通話の入力候補に BlackHole あり', mic.has ? '' : 'BlackHole未認識');
    line(!!mic.selected, '通話マイク入力 = BlackHole に選択済', mic.selected ? mic.label : '別デバイスのまま → /play で自動設定 or setup_audio.mjs');
    const muted = await yp.evaluate(() => !!document.querySelector('.ConferenceCallScreen__toolbar__item--mic-muted'));
    line(!muted, 'マイクがミュート解除されてる', muted ? 'ミュート中 → 解除が必要' : '');
  }
} catch (e) { line(false, 'CDP 9222 接続', e.message + ' → scripts/launch_yay.sh'); }

// 3) 総合判定
console.log('\n[ 判定 ]');
if (mediaState && sinkLabel && /BlackHole/i.test(sinkLabel) === true) {
  console.log('  ※ 出力先が BlackHole 単体 = 通話には流れるが【究のスピーカーには出ない】');
  console.log('    究も聞きたい → Audio MIDI設定で複数出力装置(BlackHole+スピーカー)を作り「Yay出力」と命名');
}
console.log('\n上の ✗ が音楽の止まってる場所。全部 ✓ なら通話に流れてる。\n');
process.exit(0);
