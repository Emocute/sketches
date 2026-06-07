// 通話音声の文字起こし（ローカル whisper.cpp）。
// in-page で切り出した 16kHz mono Int16 PCM(base64) を受け取り、WAV に包んで whisper-cli へ。
// 課金ゼロ・完全ローカル（Metal 加速）。モデルは Studio 共有の ggml を既定参照。
import { execFile } from 'node:child_process';
import { writeFileSync, mkdirSync, unlinkSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';

const TMP = fileURLToPath(new URL('../_listen_tmp', import.meta.url));
// 既定モデル: small（速い）。YAY_WHISPER_MODEL で large-v3-turbo 等に差し替え可。
const MODEL = process.env.YAY_WHISPER_MODEL
  || `${homedir()}/Downloads/Studio/.whisper_models/ggml-small.bin`;
const BIN = process.env.YAY_WHISPER_BIN || 'whisper-cli';
const LANG = process.env.YAY_WHISPER_LANG || 'ja';

export function modelReady() { return existsSync(MODEL); }
export function modelPath() { return MODEL; }

// whisper の無音/雑音に対する定番幻覚を弾く。
const HALLUC = [
  'ご視聴ありがとうございました', 'ご清聴ありがとうございました', 'チャンネル登録',
  'おやすみなさい', 'ありがとうございました', '[BLANK_AUDIO]', '(音楽)', '（音楽）',
  'Thanks for watching', 'Thank you for watching', 'you',
];
function clean(stdout) {
  let t = (stdout || '').split('\n').map((l) => l.trim())
    .filter((l) => l && !/^\[?whisper|^main:|^system_info|^load|^\(|^ggml_/i.test(l))
    .join(' ').trim();
  t = t.replace(/\s+/g, ' ').trim();
  if (!t) return '';
  // 記号だけ・1文字・既知幻覚は捨てる
  const bare = t.replace(/[\s。、．，!！?？…「」『』()（）.,-]/g, '');
  if (bare.length <= 1) return '';
  for (const h of HALLUC) if (t === h || (bare === h.replace(/[\s。、]/g, ''))) return '';
  // 同一文字/語の異常反復（例: "あああ…"）も捨てる
  if (/^(.)\1{6,}$/.test(bare)) return '';
  return t;
}

function wrapWav(pcmBuf, rate) {
  const dataLen = pcmBuf.length, blockAlign = 2, byteRate = rate * blockAlign;
  const h = Buffer.alloc(44);
  h.write('RIFF', 0); h.writeUInt32LE(36 + dataLen, 4); h.write('WAVE', 8);
  h.write('fmt ', 12); h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(1, 22);
  h.writeUInt32LE(rate, 24); h.writeUInt32LE(byteRate, 28); h.writeUInt16LE(blockAlign, 32); h.writeUInt16LE(16, 34);
  h.write('data', 36); h.writeUInt32LE(dataLen, 40);
  return Buffer.concat([h, pcmBuf]);
}

// base64 PCM(16k mono int16) → 文字起こし文字列（空ならノイズ扱い）。
export async function transcribe(b64, rate = 16000) {
  if (!modelReady()) throw new Error('whisper モデル無し: ' + MODEL);
  mkdirSync(TMP, { recursive: true });
  const wav = wrapWav(Buffer.from(b64, 'base64'), rate);
  const f = `${TMP}/u_${process.pid}_${Math.random().toString(36).slice(2, 9)}.wav`;
  writeFileSync(f, wav);
  try {
    // スレッド数は控えめ既定(2)。音楽配信と同居するので whisper が CPU を食い過ぎると
    //   音がぶつぶつになる。速度が要るときは YAY_WHISPER_THREADS で上げる。
    const THREADS = String(Number(process.env.YAY_WHISPER_THREADS || 2));
    const stdout = await new Promise((res, rej) => execFile(
      BIN, ['-m', MODEL, '-l', LANG, '-nt', '-t', THREADS, '-f', f],
      { maxBuffer: 8 << 20, timeout: 30000 },
      (e, so, se) => (e ? rej(new Error((se || e.message || '').slice(0, 300))) : res(so)),
    ));
    return clean(stdout);
  } finally { try { unlinkSync(f); } catch {} }
}

// --- selftest: 既定モデルで jfk.wav 等を回す（音は鳴らさない）---
if (process.argv[1] && process.argv[1].endsWith('listen.mjs') && process.argv[2] === 'selftest') {
  console.log('model:', MODEL, 'ready=', modelReady());
  process.exit(modelReady() ? 0 : 1);
}
