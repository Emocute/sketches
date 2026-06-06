// yay_music_bot 設定（純音楽BOT・YouTube一本）。
// yay_bot（究の個人用フル機能bot）とは完全独立。人格/TTS/聴取/録音/開発ツールは持たない。
export const CONFIG = {
  selfName: 'Emo Music',            // 表示名（参考）
  selfUserHref: '/user/11320230',   // bot アカウントの user id。自分の投稿除外に使用
  chatUrl: process.env.YAY_CHAT_URL || '',

  // ポーリング（コマンド取得間隔）
  pollMs: 2500,
  // 連投ガード（コマンド応答はガード対象外＝必ず返す。将来の自動通知用に残す）
  maxRepliesPerMin: 20,
  replyCooldownMs: 1500,

  // 状態ファイル（キュー/seen の永続。音楽botは軽量）
  stateFile: new URL('./state.json', import.meta.url).pathname,
};
