// 音楽 DJ エンジン（別アプリ Vivaldi で再生 → setSinkId で BlackHole 出力 → Yay 通話マイクへ）
// Vivaldi はデバッグ口付きで起動し CDP 接続する（lib/yay.mjs と同方式）。
import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';

let browser, ctx, page;

export async function connectMusic() {
  browser = await chromium.connectOverCDP(CONFIG.musicCdpUrl);
  const all = browser.contexts().flatMap((c) => c.pages());
  page = all.find((p) => /youtube|spotify/.test(p.url())) || all[0];
  ctx = page ? page.context() : browser.contexts()[0];
  if (!page) page = await ctx.newPage();
  // 待機ページが about:blank だと secure context でなく mediaDevices/setSinkId が使えない。
  // アイドル時だけ YouTube（実オリジン）へ寄せる。再生中(youtube/spotify)なら触らない。
  if (/^about:blank/.test(page.url())) {
    try { await page.goto('https://www.youtube.com/', { waitUntil: 'domcontentloaded' }); } catch {}
  }
  try { await ctx.grantPermissions(['microphone'], { origin: 'https://www.youtube.com' }); } catch {}
  return { browser, ctx, page };
}

// 出力デバイスを探して、以後の audio/video を全部そこへ流す。
// 優先順位: CONFIG.sinkPrefer の順（Multi-Output で試聴も = 究も聞ける）→ 無ければ BlackHole。
// setSinkId が本当に適用されたか・再生が進んでるかまで検証して返す（DRM/WebAudio で黙って失敗する罠対策）。
export async function routeToBlackHole(p = page) {
  return p.evaluate(async (prefer) => {
    // 出力デバイスのラベルを露出させるため一度マイクを掴む（--use-fake-ui で自動許可・無音）
    try { const s = await navigator.mediaDevices.getUserMedia({ audio: true }); s.getTracks().forEach((t) => t.stop()); } catch {}
    const devs = await navigator.mediaDevices.enumerateDevices();
    const outs = devs.filter((d) => d.kind === 'audiooutput');
    let dev = null;
    for (const m of prefer) { dev = outs.find((d) => new RegExp(m, 'i').test(d.label)); if (dev) break; }
    if (!dev) return { ok: false, reason: 'BlackHole 出力なし', labels: outs.map((d) => d.label) };
    window.__yaybotSink = dev.deviceId;

    const setOne = (el) => el.setSinkId ? el.setSinkId(dev.deviceId).then(() => true).catch((e) => e.name) : 'no-setSinkId';
    const apply = () => Promise.all([...document.querySelectorAll('audio,video')].map(setOne));
    const results = await apply();
    // MutationObserver で後から生える要素にも貼り続ける
    if (!window.__yaybotObs) {
      window.__yaybotObs = new MutationObserver(() => apply());
      window.__yaybotObs.observe(document.documentElement, { subtree: true, childList: true });
    }

    // 検証：少し待って実際の状態を観測
    await new Promise((r) => setTimeout(r, 1200));
    const els = [...document.querySelectorAll('audio,video')];
    const media = els.map((el) => ({
      sink: el.sinkId || 'default',
      onTarget: el.sinkId === dev.deviceId,
      paused: el.paused, muted: el.muted, vol: el.volume,
      t: Math.round(el.currentTime * 10) / 10,
    }));
    const routed = media.filter((m) => m.onTarget);
    const playing = media.filter((m) => !m.paused && !m.muted && m.vol > 0 && m.t > 0);
    return {
      ok: routed.length > 0 && playing.length > 0,
      device: dev.label,
      sinkErrors: results.filter((r) => r !== true && r !== 'no-setSinkId'),
      routedCount: routed.length, playingCount: playing.length, mediaCount: els.length,
      reason: routed.length === 0 ? 'setSinkId 不適用(DRM/WebAudio の可能性→/yt推奨)'
            : playing.length === 0 ? '再生が始まってない(ログイン/選曲失敗?)' : '',
      media,
    };
  }, CONFIG.sinkPrefer);
}

export async function playYouTube(query) {
  // 検索結果から1件目を開く。consent クッキー壁が出たら飛ばす。
  await page.goto('https://www.youtube.com/results?search_query=' + encodeURIComponent(query), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  await page.locator('button[aria-label*="同意"], button[aria-label*="Accept"]').first().click({ timeout: 1500 }).catch(() => {});
  await page.locator('a#video-title, ytd-video-renderer a#thumbnail').first().click().catch(() => {});
  await page.waitForTimeout(2500);
  // 自動再生が止まってたら明示 play（広告含め鳴らす）
  await page.evaluate(() => document.querySelector('video')?.play?.().catch(() => {}));
  await page.waitForTimeout(800);
  return { service: 'youtube', query, route: await routeToBlackHole() };
}

// Spotify Web は Widevine DRM のため setSinkId が弾かれる場合がある（→ /yt を既定推奨）。
// 既契約 Premium 前提。未ログイン/無料だと再生が始まらない。
export async function playSpotify(query) {
  await page.goto('https://open.spotify.com/search/' + encodeURIComponent(query) + '/tracks', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await page.locator('[data-testid="track-list"] [role="row"]').first().dblclick().catch(() => {});
  await page.waitForTimeout(2000);
  return { service: 'spotify', query, route: await routeToBlackHole() };
}

// keepalive：アイドルの音楽ブラウザは OS に回収されやすい。CDP で定期的に触って生かす
// （Yay 側が bot のポーリングで生き続けるのと同じ理屈）。落ちてたら再接続を試みる。
export async function ping() {
  try {
    if (!browser || !browser.isConnected()) return false;
    await page.evaluate(() => 1);
    return true;
  } catch { return false; }
}

export async function setVolume(level /* 0..1 */) {
  return page.evaluate((v) => document.querySelectorAll('audio,video').forEach((el) => (el.volume = v)), level);
}
export async function pause() {
  return page.evaluate(() => document.querySelectorAll('audio,video').forEach((el) => el.pause()));
}
