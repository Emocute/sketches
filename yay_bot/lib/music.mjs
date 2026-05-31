// 音楽 DJ エンジン（別アプリ Vivaldi で再生 → setSinkId で BlackHole 出力 → Yay 通話マイクへ）
// Vivaldi はデバッグ口付きで起動し CDP 接続する（lib/yay.mjs と同方式）。
import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';

let browser, ctx, page;

export async function connectMusic() {
  browser = await chromium.connectOverCDP(CONFIG.musicCdpUrl);
  ctx = browser.contexts()[0];
  try { await ctx.grantPermissions(['microphone']); } catch {}
  page = ctx.pages().find((p) => /youtube|spotify/.test(p.url())) || ctx.pages()[0] || (await ctx.newPage());
  return { browser, ctx, page };
}

// BlackHole 出力デバイスを探して、以後の audio/video を全部そこへ流す
export async function routeToBlackHole(p = page) {
  return p.evaluate(async (match) => {
    // 出力デバイスのラベルを露出させるため一度マイクを掴む（--use-fake-ui で自動許可・無音）
    try { const s = await navigator.mediaDevices.getUserMedia({ audio: true }); s.getTracks().forEach((t) => t.stop()); } catch {}
    const devs = await navigator.mediaDevices.enumerateDevices();
    const outs = devs.filter((d) => d.kind === 'audiooutput');
    const bh = outs.find((d) => d.label.includes(match));
    if (!bh) return { ok: false, reason: 'BlackHole 出力なし', labels: outs.map((d) => d.label) };
    window.__yaybotSink = bh.deviceId;
    const apply = () => document.querySelectorAll('audio,video').forEach((el) => el.setSinkId && el.setSinkId(bh.deviceId).catch(() => {}));
    apply();
    if (!window.__yaybotObs) {
      window.__yaybotObs = new MutationObserver(apply);
      window.__yaybotObs.observe(document.documentElement, { subtree: true, childList: true });
    }
    return { ok: true, deviceId: bh.deviceId, label: bh.label };
  }, CONFIG.sinkLabelMatch);
}

export async function playYouTube(query) {
  await page.goto('https://www.youtube.com/results?search_query=' + encodeURIComponent(query), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  await page.locator('a#video-title, ytd-video-renderer a#thumbnail').first().click();
  await page.waitForTimeout(2500);
  return { service: 'youtube', query, route: await routeToBlackHole() };
}

export async function playSpotify(query) {
  await page.goto('https://open.spotify.com/search/' + encodeURIComponent(query) + '/tracks', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await page.locator('[data-testid="track-list"] [role="row"]').first().dblclick().catch(() => {});
  await page.waitForTimeout(2000);
  return { service: 'spotify', query, route: await routeToBlackHole() };
}

export async function setVolume(level /* 0..1 */) {
  return page.evaluate((v) => document.querySelectorAll('audio,video').forEach((el) => (el.volume = v)), level);
}
export async function pause() {
  return page.evaluate(() => document.querySelectorAll('audio,video').forEach((el) => el.pause()));
}
