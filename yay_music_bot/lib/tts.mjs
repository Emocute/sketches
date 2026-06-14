// 読み上げ（TTS）。bot の返信を音声化して Agora RTC に直 publish する。
// 経路: speak(text) → Voicevox or macOS say で WAV 生成 → ファイル保存 → 返す
//      bot が WAV ファイルパスを playUrl(agora_client) で即 publish
//
// エンジン優先:
//   1) VOICEVOX engine（http://127.0.0.1:50021）が生きてれば → 本物のずんだもん声（speaker=3）
//   2) 無ければ macOS `say`（既定 Kyoko）で WAV 生成。即動くがずんだもん音色ではない。
// 課金ゼロ・完全ローカル。
import { execFile, spawn } from 'node:child_process';
import { createHmac } from 'node:crypto';
import { writeFileSync, readFileSync, mkdirSync, unlinkSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const TMP = fileURLToPath(new URL('../_tts_tmp', import.meta.url));
const VV_URL = process.env.YAY_VOICEVOX_URL || 'http://127.0.0.1:50021';
const VV_SPEAKER = Number(process.env.YAY_VOICEVOX_SPEAKER || 3); // 3 = ずんだもん(ノーマル)
const SAY_VOICE = process.env.YAY_SAY_VOICE || 'Kyoko';

// ボイスパック（Voicevox speaker ID）
export const VOICE_PACKS = {
  kiritan: { name: '東北きりたん（ノーマル）', speaker: 108, engine: 'voicevox', speed: 1.0 },   // 究の既定(2026-06-14)・速度は普通
  zundamon: { name: 'ずんだもん（ノーマル）', speaker: 3, engine: 'voicevox' },
  zundamon_power: { name: 'ずんだもん（パワフル）', speaker: 75, engine: 'voicevox' },
  zundamon_sad: { name: 'ずんだもん（悲しい）', speaker: 74, engine: 'voicevox' },
  sora: { name: 'そら', speaker: 0, engine: 'voicevox' },
  akari: { name: 'あかり', speaker: 10, engine: 'voicevox' },
  mafuyu: { name: 'まふゆ', speaker: 12, engine: 'voicevox' },
  say_default: { name: 'Kyoko（macOS）', engine: 'say', voice: 'Kyoko' },
  // CoeFont 公式「ひろゆき」(西村博之本人ボイス、音声利用は0pt)。要 API キー（Plusプラン）。
  // 未設定時は say(Kyoko)へ自動フォールバック。coefont = ひろゆきの voice UUID。
  hiroyuki: { name: 'ひろゆき（CoeFont）', engine: 'coefont', coefont: '19d55439-312d-4a1d-a27b-28f0f31bedc5', voice: 'Kyoko' },
};

// CoeFont API（HMAC-SHA256 認証）。text → wav バイナリ。キー未設定なら例外（呼び出し側で say へ落ちる）。
const CF_KEY = () => process.env.COEFONT_ACCESSKEY || '';
const CF_SECRET = () => process.env.COEFONT_SECRET || '';
export function coefontConfigured() { return !!(CF_KEY() && CF_SECRET()); }
async function viaCoeFont(text, coefontId) {
  const key = CF_KEY(), secret = CF_SECRET();
  if (!key || !secret) throw new Error('COEFONT_ACCESSKEY/SECRET 未設定');
  const date = String(Math.floor(Date.now() / 1000));
  const body = JSON.stringify({ coefont: coefontId, text: text.slice(0, 1000), format: 'wav' });
  const sig = createHmac('sha256', secret).update(date + body).digest('hex');
  const r = await fetch('https://api.coefont.cloud/v2/text2speech', {
    method: 'POST', redirect: 'follow', signal: AbortSignal.timeout(20000),
    headers: { 'Content-Type': 'application/json', Authorization: key, 'X-Coefont-Date': date, 'X-Coefont-Content': sig },
    body,
  });
  if (!r.ok) throw new Error('coefont ' + r.status + ' ' + (await r.text().catch(() => '')).slice(0, 120));
  return Buffer.from(await r.arrayBuffer());
}

let _vvAlive = null; // キャッシュ（null=未確認）
export async function voicevoxAlive() {
  try {
    const r = await fetch(`${VV_URL}/version`, { signal: AbortSignal.timeout(1500) });
    _vvAlive = r.ok; return r.ok;
  } catch { _vvAlive = false; return false; }
}
export function engineName() { return _vvAlive ? `voicevox(spk${VV_SPEAKER})` : `say(${SAY_VOICE})`; }

// 読み上げ用にテキストを整える（絵文字・コマンド記号・URL を除去）。
export function sanitize(text) {
  let t = String(text || '');
  t = t.replace(/^[!\/]\S*\s*/, '');                 // 先頭コマンド痕
  t = t.replace(/https?:\/\/\S+/g, '');              // URL
  t = t.replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2B00}-\u{2BFF}️]/gu, ''); // 絵文字・記号
  t = t.replace(/\s+/g, ' ').trim();
  return t.slice(0, 180);                             // 長すぎ防止
}

async function viaVoicevox(text, speaker = VV_SPEAKER, speed = 1) {
  const q = await fetch(`${VV_URL}/audio_query?speaker=${speaker}&text=${encodeURIComponent(text)}`,
    { method: 'POST', signal: AbortSignal.timeout(8000) });
  if (!q.ok) throw new Error('audio_query ' + q.status);
  const query = await q.json();
  if (speed && speed !== 1) query.speedScale = speed;   // 発音速度（1=標準、>1で早口）
  const s = await fetch(`${VV_URL}/synthesis?speaker=${speaker}`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(query), signal: AbortSignal.timeout(15000) });
  if (!s.ok) throw new Error('synthesis ' + s.status);
  const wav = Buffer.from(await s.arrayBuffer());
  return wav;
}

async function viaSay(text, voice = SAY_VOICE) {
  // say は /dev/stdout への出力が macOS で失敗する(-54)ので、一時 WAV へ出して読み戻す。
  // --data-format=LEI16@24000 + .wav 拡張子 で RIFF WAV(PCM) を生成（VOICEVOX 経路と同じ wav 形式）。
  mkdirSync(TMP, { recursive: true });
  const tmpf = `${TMP}/sayraw_${process.pid}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.wav`;
  await new Promise((res, rej) => {
    const p = spawn('say', ['-v', voice, '-r', '180', '--data-format=LEI16@24000', '-o', tmpf, text], { stdio: ['ignore', 'ignore', 'ignore'] });
    p.on('close', (code) => (code === 0 ? res() : rej(new Error('say exit ' + code))));
    p.on('error', rej);
  });
  const buf = readFileSync(tmpf);
  try { unlinkSync(tmpf); } catch {}
  return buf;
}

// テキストを音声化して WAV ファイルに保存。ファイルパスを返す（Agora playUrl 用）。
// voice = ボイスパックキー（VOICE_PACKS の key）。無ければ既定。
export async function speak(text, { voice = null } = {}) {
  const t = sanitize(text);
  if (!t) return { ok: false, skipped: true };

  // ボイスパックを解決
  let pack = null;
  if (voice && VOICE_PACKS[voice]) {
    pack = VOICE_PACKS[voice];
  }

  let wav = null;
  let usedEngine = 'say';

  // 1) CoeFont（ひろゆき等の外部AI音声、APIキー要）。失敗時は say へ落ちる。
  if (pack?.engine === 'coefont') {
    try { wav = await viaCoeFont(t, pack.coefont); usedEngine = 'coefont'; }
    catch (e) { console.error('[tts] coefont 失敗→sayへ:', e.message); }
  }

  // 2) VOICEVOX（ローカル）
  if (!wav && pack?.engine !== 'coefont') {
    if (_vvAlive === null) await voicevoxAlive();
    try {
      if (pack?.engine === 'voicevox' || (_vvAlive && !pack)) {
        if (_vvAlive) {
          const sp = Number(process.env.YAY_TTS_SPEED) || pack?.speed || 1;   // 速度: env優先→パック既定→1
          wav = await viaVoicevox(t, pack?.speaker ?? VV_SPEAKER, sp); usedEngine = 'voicevox';
        }
      }
    } catch (e) { _vvAlive = false; /* VOICEVOX落ちたら say へ落ちる */ }
  }

  // 3) macOS say フォールバック
  if (!wav) {
    wav = await viaSay(t, pack?.voice ?? SAY_VOICE);
    usedEngine = 'say';
  }

  mkdirSync(TMP, { recursive: true });
  const f = `${TMP}/say_${process.pid}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.wav`;
  writeFileSync(f, wav);
  return { ok: true, engine: usedEngine, voice: voice || 'default', file: f };
}

if (process.argv[1] && process.argv[1].endsWith('tts.mjs') && process.argv[2] === 'selftest') {
  await voicevoxAlive();
  console.log('engine:', engineName());
  process.exit(0);
}
