// yay_music_bot 設定（純音楽BOT・YouTube一本）。
// yay_bot（究の個人用フル機能bot）とは完全独立。会話/人格/聴取/録音/開発ツールは持たない。
// 唯一の例外＝入退室の読み上げ（誰が来た/帰ったを名前で短く言うだけ。LLMは一切使わない）。
export const CONFIG = {
  selfName: 'Emo Music',            // 表示名（参考）
  selfUserHref: '/user/11320230',   // bot アカウントの user id。自分の投稿除外に使用
  chatUrl: process.env.YAY_CHAT_URL || '',

  // ポーリング（コマンド取得間隔）
  pollMs: 2500,
  // 連投ガード（コマンド応答はガード対象外＝必ず返す。将来の自動通知用に残す）
  maxRepliesPerMin: 20,
  replyCooldownMs: 1500,

  // 入退室の読み上げ（純音楽botに足した唯一の声機能。LLM不使用＝コンテキスト消費ゼロ）。
  //   名簿(yay_api.py members)を周期取得→前回との差分で join/leave を検出し、
  //   チャットに短い一言＋TTS(VOICEVOX無ければ macOS say Kyoko)で読み上げる。
  jingle: {
    enabled: true,        // 既定ON（/greet off で停止）
    voice: true,          // 声でも読む（false=チャット文字だけ）
    ttsVol: 40,           // 読み上げの初期音量 0-100（15小/90大/50やや大→40に調整。究指示2026-06-14。/ttsvol で変更）
    voiceKey: 'kiritan',  // TTSボイス。究指示2026-06-14「東北きりたん・早めの発音」→ VOICEVOX 東北きりたん(spk108, speed1.2)。VOICEVOX落ちてたら自動でmacOS sayへ。YAY_VOICE/YAY_TTS_SPEED env で上書き可
    pollMs: 12000,        // 名簿ポーリング間隔
    minGapMs: 8000,       // 連続あいさつの最小間隔（連打防止）
    maxQueue: 8,          // あいさつ待ち行列の上限（溢れたら古いの捨て）
    rejoinGraceMs: 90000, // この時間内の再入室は「おかえり」扱い
    quietHours: null,     // 例 [23, 7] で23時〜7時は声を出さない（文字は出す）。null=常時OK
  },

  // 状態ファイル（キュー/seen の永続。音楽botは軽量）
  stateFile: new URL('./state.json', import.meta.url).pathname,
};
