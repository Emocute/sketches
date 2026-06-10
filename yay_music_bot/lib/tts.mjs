// 読み上げ（TTS）。bot の返信を音声化して Agora RTC に直 publish する。
// 経路: speak(text) → Voicevox or macOS say で WAV 生成 → ファイル保存 → 返す
//      bot が WAV ファイルパスを playUrl(agora_client) で即 publish
//
// エンジン優先:
//   1) VOICEVOX engine（http://127.0.0.1:50021）が生きてれば → 本物のずんだもん声（speaker=3）
//   2) 無ければ macOS `say`（既定 Kyoko）で WAV 生成。即動くがずんだもん音色ではない。
// 課金ゼロ・完全ローカル。
import { execFile, spawn } from 'node:child_process';
import { writeFileSync, mkdirSync, unlinkSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const TMP = fileURLToPath(new URL('../_tts_tmp', import.meta.url));
const VV_URL = process.env.YAY_VOICEVOX_URL || 'http://127.0.0.1:50021';
const VV_SPEAKER = Number(process.env.YAY_VOICEVOX_SPEAKER || 3); // 3 = ずんだもん(ノーマル)
const SAY_VOICE = process.env.YAY_SAY_VOICE || 'Kyoko';

// ボイスパック（Voicevox speaker ID）
export const VOICE_PACKS = {
  zundamon: { name: 'ずんだもん（ノーマル）', speaker: 3, engine: 'voicevox' },
  zundamon_power: { name: 'ずんだもん（パワフル）', speaker: 75, engine: 'voicevox' },
  zundamon_sad: { name: 'ずんだもん（悲しい）', speaker: 74, engine: 'voicevox' },
  sora: { name: 'そら', speaker: 0, engine: 'voicevox' },
  akari: { name: 'あかり', speaker: 10, engine: 'voicevox' },
  mafuyu: { name: 'まふゆ', speaker: 12, engine: 'voicevox' },
  say_default: { name: 'Kyoko（macOS）', engine: 'say', voice: 'Kyoko' },
};

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

async function viaVoicevox(text, speaker = VV_SPEAKER) {
  const q = await fetch(`${VV_URL}/audio_query?speaker=${speaker}&text=${encodeURIComponent(text)}`,
    { method: 'POST', signal: AbortSignal.timeout(8000) });
  if (!q.ok) throw new Error('audio_query ' + q.status);
  const query = await q.text();
  const s = await fetch(`${VV_URL}/synthesis?speaker=${speaker}`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: query, signal: AbortSignal.timeout(15000) });
  if (!s.ok) throw new Error('synthesis ' + s.status);
  const wav = Buffer.from(await s.arrayBuffer());
  return wav;
}

async function viaSay(text, voice = SAY_VOICE) {
  // say コマンドで WAV を標準出力に出す
  return new Promise((res, rej) => {
    const p = spawn('say', ['-v', voice, '-r', '180', '-o', '/dev/stdout', text], { stdio: ['ignore', 'pipe', 'ignore'] });
    const chunks = [];
    p.stdout.on('data', (d) => chunks.push(d));
    p.on('close', (code) => {
      if (code === 0) res(Buffer.concat(chunks));
      else rej(new Error('say exit ' + code));
    });
    p.on('error', rej);
  });
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

  if (_vvAlive === null) await voicevoxAlive();
  let wav = null;
  let usedEngine = 'say';

  try {
    if (pack?.engine === 'voicevox' || (_vvAlive && !pack)) {
      if (_vvAlive) {
        const speaker = pack?.speaker ?? VV_SPEAKER;
        wav = await viaVoicevox(t, speaker);
        usedEngine = 'voicevox';
      }
    }
  } catch (e) { _vvAlive = false; /* VOICEVOX落ちたら say へ落ちる */ }

  if (!wav) {
    const v = pack?.voice ?? SAY_VOICE;
    wav = await viaSay(t, v);
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
