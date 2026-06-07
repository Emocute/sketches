// 音源リゾルバ（Agora版）。/play <query> を「ローカルの音声ファイル絶対パス」に解決する。
// Agoraの BufferSourceAudioTrack は音声ファイル/URLを取り込む方式なので、
// YouTube等のページではなく "実体の音声" が要る。yt-dlp で bestaudio を取得しキャッシュ配信する。
//
// 解決順:
//   1) 絶対パスの既存音声ファイル → そのまま
//   2) http(s) の直リンク音声 → そのまま（ページ側がfetch）
//   3) それ以外（曲名/URL） → yt-dlp で bestaudio をキャッシュにDL → そのパス
import { execFile } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const CACHE = fileURLToPath(new URL('../_music_cache', import.meta.url));
const AUDIO_EXT = /\.(mp3|m4a|aac|ogg|opus|wav|flac)$/i;
const sh = (cmd, args, opts = {}) => new Promise((res, rej) => {
  execFile(cmd, args, { maxBuffer: 16 << 20, timeout: opts.timeout || 120000 }, (e, so, se) => (e ? rej(new Error((se || e.message || '').slice(0, 400))) : res(so)));
});

function cacheHit(key) {
  if (!existsSync(CACHE)) return null;
  const f = readdirSync(CACHE).find((n) => n.startsWith(key + '.') && AUDIO_EXT.test(n));
  return f ? `${CACHE}/${f}` : null;
}

// 曲名/URL → bestaudio をキャッシュにDLして絶対パスを返す
export async function ytdlpToFile(query, { timeout = 120000 } = {}) {
  mkdirSync(CACHE, { recursive: true });
  const isUrl = /^https?:\/\//i.test(query);
  const target = isUrl ? query : `ytsearch1:${query}`;
  const key = createHash('sha1').update(target).digest('hex').slice(0, 16);
  const hit = cacheHit(key);
  if (hit) return { path: hit, cached: true, query };
  // bestaudio を m4a に。出力名は key 固定。
  const out = `${CACHE}/${key}.%(ext)s`;
  await sh('yt-dlp', ['-x', '--audio-format', 'm4a', '--audio-quality', '0', '-f', 'bestaudio/best', '--no-playlist', '-o', out, target], { timeout });
  const made = cacheHit(key);
  if (!made) throw new Error('yt-dlp 出力が見つからない');
  return { path: made, cached: false, query };
}

// /play 入力 → 直リンク音声URL（DLしない。yt-dlp -g で一瞬取るだけ＝real-time配信用）。
//   既に直リンク音声URLならそのまま返す。曲名/ページURLは yt-dlp -g で bestaudio の直URLに解決。
export async function resolveStreamUrl(query, { timeout = 30000 } = {}) {
  const q = (query || '').trim();
  if (!q) throw new Error('曲名が空');
  if (/^https?:\/\/.+\.(mp3|m4a|aac|ogg|opus|wav|flac)(\?|$)/i.test(q)) return { url: q, query: q };
  const target = /^https?:\/\//i.test(q) ? q : `ytsearch1:${q}`;
  // m4a(itag140)優先。-g は URL のみ出力（DLなし）。--print で正式タイトルも同時取得。
  const out = await sh('yt-dlp', ['-g', '--print', 'T:%(title)s', '-f', 'bestaudio[ext=m4a]/bestaudio/best', '--no-playlist', target], { timeout });
  const lines = (out || '').trim().split('\n').filter(Boolean);
  const url = lines.filter((l) => /^https?:\/\//.test(l)).pop();
  const tline = lines.find((l) => l.startsWith('T:'));
  const title = tline ? tline.slice(2).trim() : q;
  if (!url) throw new Error('yt-dlp がURLを返さない');
  return { url, title, query: q };
}

// YouTube プレイリストURL → 各動画 {url,title} の配列（--flat-playlist で軽量列挙、DLしない）。
//   先頭 limit 件のみ取得。展開できなければ空配列を返す（呼び出し側で単曲扱いにフォールバック）。
export async function expandPlaylist(url, { timeout = 60000, limit = 100 } = {}) {
  let out;
  try {
    out = await sh('yt-dlp', ['--flat-playlist', '--no-warnings', '-I', `1:${limit}`,
      '--print', '%(url)s\t%(title)s', url], { timeout });
  } catch (e) {
    throw new Error('playlist 展開失敗: ' + (e.message || '').slice(0, 200));
  }
  return (out || '').trim().split('\n').filter(Boolean).map((l) => {
    const i = l.indexOf('\t');
    const u = (i < 0 ? l : l.slice(0, i)).trim();
    const t = (i < 0 ? '' : l.slice(i + 1)).trim();
    return { url: u, title: t || u };
  }).filter((x) => /^https?:\/\//.test(x.url));
}

// /play 入力 → { path } （ローカル絶対パス、旧DL方式。フォールバック用に残置）
export async function resolve(query) {
  const q = (query || '').trim();
  if (!q) throw new Error('曲名が空');
  if (q.startsWith('/') && existsSync(q) && AUDIO_EXT.test(q)) return { path: q, cached: true, query: q };
  if (/^https?:\/\/.+\.(mp3|m4a|aac|ogg|opus|wav|flac)(\?|$)/i.test(q)) return { directUrl: q, query: q };
  return ytdlpToFile(q);
}

// --- selftest: yt-dlp 解決を1曲だけ試す（究が音を出したくない時は走らせない）---
if (process.argv[1] && process.argv[1].endsWith('music_agora.mjs') && process.argv[2] === 'selftest') {
  const q = process.argv.slice(3).join(' ') || 'lofi hip hop';
  console.log('resolving:', q);
  resolve(q).then((r) => { console.log('OK', r); process.exit(0); }).catch((e) => { console.error('FAIL', e.message); process.exit(1); });
}
