// 読み上げ（TTS）。bot の返信を音声化して Agora RTC に直 publish する。
// 経路: speak(text) → Voicevox or macOS say で WAV 生成 → ファイル保存 → 返す
//      bot が WAV ファイルパスを playUrl(agora_client) で即 publish
//
// エンジン優先:
//   1) VOICEVOX engine（http://127.0.0.1:50021）が生きてれば → 本物のずんだもん声（speaker=3）
//   2) 無ければ macOS `say`（既定 Kyoko）で WAV 生成。即動くがずんだもん音色ではない。
// 課金ゼロ・完全ローカル。
import { execFile, spawn } from 'node:child_process';
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
  english: { name: 'Daniel（英・macOS）', engine: 'say', voice: 'Daniel' },   // 英語モード（究指示2026-06-14）
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

  // 1) VOICEVOX（ローカル）
  if (!wav) {
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

// ===== 日本語→ローマ字（英語モードで Daniel に無理やり読ませる用。LLM不使用＝トークン消費ゼロ）=====
// 漢字の読みは VOICEVOX(ローカル) の audio_query.kana を借りる。カナ→ローマ字は下のテーブルで機械変換。
function hiraToKata(s) { return String(s).replace(/[ぁ-ゖ]/g, (c) => String.fromCharCode(c.charCodeAt(0) + 0x60)); }
const YOUON = {
  キャ: 'kya', キュ: 'kyu', キョ: 'kyo', シャ: 'sha', シュ: 'shu', ショ: 'sho', シェ: 'she',
  チャ: 'cha', チュ: 'chu', チョ: 'cho', チェ: 'che', ニャ: 'nya', ニュ: 'nyu', ニョ: 'nyo',
  ヒャ: 'hya', ヒュ: 'hyu', ヒョ: 'hyo', ミャ: 'mya', ミュ: 'myu', ミョ: 'myo',
  リャ: 'rya', リュ: 'ryu', リョ: 'ryo', ギャ: 'gya', ギュ: 'gyu', ギョ: 'gyo',
  ジャ: 'ja', ジュ: 'ju', ジョ: 'jo', ジェ: 'je', ビャ: 'bya', ビュ: 'byu', ビョ: 'byo',
  ピャ: 'pya', ピュ: 'pyu', ピョ: 'pyo', ティ: 'ti', トゥ: 'tu', ディ: 'di', ドゥ: 'du',
  ファ: 'fa', フィ: 'fi', フェ: 'fe', フォ: 'fo', ウィ: 'wi', ウェ: 'we', ウォ: 'wo',
  ヴァ: 'va', ヴィ: 'vi', ヴェ: 've', ヴォ: 'vo', ツァ: 'tsa', ツェ: 'tse', ツォ: 'tso',
};
const ROMA = {
  ア: 'a', イ: 'i', ウ: 'u', エ: 'e', オ: 'o', カ: 'ka', キ: 'ki', ク: 'ku', ケ: 'ke', コ: 'ko',
  サ: 'sa', シ: 'shi', ス: 'su', セ: 'se', ソ: 'so', タ: 'ta', チ: 'chi', ツ: 'tsu', テ: 'te', ト: 'to',
  ナ: 'na', ニ: 'ni', ヌ: 'nu', ネ: 'ne', ノ: 'no', ハ: 'ha', ヒ: 'hi', フ: 'fu', ヘ: 'he', ホ: 'ho',
  マ: 'ma', ミ: 'mi', ム: 'mu', メ: 'me', モ: 'mo', ヤ: 'ya', ユ: 'yu', ヨ: 'yo',
  ラ: 'ra', リ: 'ri', ル: 'ru', レ: 're', ロ: 'ro', ワ: 'wa', ヲ: 'o', ン: 'n',
  ガ: 'ga', ギ: 'gi', グ: 'gu', ゲ: 'ge', ゴ: 'go', ザ: 'za', ジ: 'ji', ズ: 'zu', ゼ: 'ze', ゾ: 'zo',
  ダ: 'da', ヂ: 'ji', ヅ: 'zu', デ: 'de', ド: 'do', バ: 'ba', ビ: 'bi', ブ: 'bu', ベ: 'be', ボ: 'bo',
  パ: 'pa', ピ: 'pi', プ: 'pu', ペ: 'pe', ポ: 'po', ヴ: 'vu',
  ァ: 'a', ィ: 'i', ゥ: 'u', ェ: 'e', ォ: 'o', ヤ_: 'ya',
};
function kanaToRomaji(input) {
  const kata = hiraToKata(input);
  let out = '', sokuon = false;
  for (let i = 0; i < kata.length; i++) {
    const c = kata[i], pair = kata.substr(i, 2);
    if (c === 'ッ') { sokuon = true; continue; }
    if (c === 'ー') { const m = out.match(/[aeiou]$/); if (m) out += m[0]; continue; }
    let r;
    if (YOUON[pair]) { r = YOUON[pair]; i++; }
    else if (ROMA[c] !== undefined) { r = ROMA[c]; }
    else { r = ''; }
    if (sokuon) { if (/^[a-z]/.test(r)) out += r[0]; sokuon = false; }
    out += r;
  }
  return out;
}
async function vvKana(text) {
  const r = await fetch(`${VV_URL}/audio_query?speaker=${VV_SPEAKER}&text=${encodeURIComponent(text)}`,
    { method: 'POST', signal: AbortSignal.timeout(8000) });
  if (!r.ok) throw new Error('kana ' + r.status);
  const q = await r.json();
  return String(q.kana || '').replace(/[^゠-ヿー]/g, '');   // カタカナとーだけ残す
}
// 文字列中の日本語を機械的にローマ字へ。英語等はそのまま。漢字は VOICEVOX で読みを取得。
export async function toRomaji(text) {
  const t = String(text || '');
  if (!/[぀-ヿ一-鿿]/.test(t)) return t;   // 日本語なし→そのまま
  const segs = t.split(/([぀-ヿ一-鿿]+)/);
  let out = '';
  for (const s of segs) {
    if (!s) continue;
    if (/[぀-ヿ一-鿿]/.test(s)) {
      let kata = null;
      if (/[一-鿿]/.test(s)) { try { kata = await vvKana(s); } catch {} }   // 漢字含む→VOICEVOXで読み
      if (!kata) kata = hiraToKata(s);
      const ro = kanaToRomaji(kata);
      out += ro ? ` ${ro} ` : '';
    } else out += s;
  }
  return out.replace(/\s+/g, ' ').trim();
}

if (process.argv[1] && process.argv[1].endsWith('tts.mjs') && process.argv[2] === 'selftest') {
  await voicevoxAlive();
  console.log('engine:', engineName());
  process.exit(0);
}
