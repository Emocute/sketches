import { chromium } from 'playwright';
import { CONFIG } from '../config.mjs';
setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 20000);
const browser = await chromium.connectOverCDP(CONFIG.musicCdpUrl);
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /spotify/.test(p.url())) || ctx.pages()[0];
await page.waitForTimeout(2000);
const r = await page.evaluate(async (match) => {
  let micOk = false;
  try { const s = await navigator.mediaDevices.getUserMedia({ audio: true }); s.getTracks().forEach(t => t.stop()); micOk = true; } catch (e) { micOk = 'err:' + e.name; }
  const outs = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'audiooutput');
  const bh = outs.find(d => (d.label || '').includes(match));
  let sinkOk = null;
  if (bh) { try { const a = new Audio(); sinkOk = a.setSinkId ? (await a.setSinkId(bh.deviceId), 'OK') : 'unsupported'; } catch (e) { sinkOk = 'err:' + e.name; } }
  return { micOk, labels: outs.map(d => d.label), bh: bh ? bh.label : null, sinkOk };
}, CONFIG.sinkLabelMatch);
console.log(JSON.stringify(r, null, 1));
process.exit(0);
