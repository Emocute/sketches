// yay_bot 設定
export const CONFIG = {
  // 専用プロファイル（実 Chrome）。窓はデバッグ口付きで起動し CDP 接続する
  yayProfile: '/Users/emocute/.claude/playwright-profile-yay',
  cdpUrl: 'http://localhost:9222',
  selfName: 'Emo Claude', // 表示名（参考）
  selfUserHref: '/user/11320230', // Emo Claude の user id。自分の投稿はこれで確実に除外（名前パースに依存しない）
  // 音楽用ブラウザ（別アプリ＝OS で音を分離できる）。Vivaldi 専用プロファイル
  musicProfile: '/Users/emocute/.claude/playwright-profile-music',
  vivaldiPath: '/Applications/Vivaldi.app/Contents/MacOS/Vivaldi',
  musicCdpUrl: 'http://localhost:9223', // Vivaldi をデバッグ口付きで起動して接続

  // 対象チャット（究が URL をくれたら差し込む）
  chatUrl: process.env.YAY_CHAT_URL || '',

  // ポーリング
  pollMs: 7000, // 10s（反応を詰めた）
  idleBackoffMs: 30000, // 無活動が続いたら 45s に伸ばす
  maxRepliesPerMin: 10, // 自己ループは href 除外で根絶済なので緩め（暴走バックストップのみ）
  replyCooldownMs: 3000, // 最低クールダウンも短く（返せない方が問題）

  // 状態ファイル
  stateFile: new URL('./state.json', import.meta.url).pathname,

  // 音声: setSinkId で音楽タブの出力を BlackHole へ
  sinkLabelMatch: 'BlackHole',

  // ===== Yay DOM セレクタ（2026-06-01 実画面で較正済）=====
  selectors: {
    chatToggle: '.ConferenceCallScreen__toolbar__item--chat',
    bgmToggle: '.ConferenceCallScreen__toolbar__item--bgm',
    messageRow: '.Messages__item',
    messageImg: '.Messages__item__img', // href="/user/<id>"、img alt="〇〇のカバー写真"
    messageText: '.Messages__item__span--text',
    messageTime: '.Messages__item__time',
    inputBox: 'textarea.CallChatReplyForm__form__input',
    sendButton: 'button.Button--icon-chat-send',
  },
};
