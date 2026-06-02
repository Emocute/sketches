// yay_bot 設定
export const CONFIG = {
  // 専用プロファイル（実 Chrome）。窓はデバッグ口付きで起動し CDP 接続する
  yayProfile: '/Users/emocute/.claude/playwright-profile-yay',
  cdpUrl: 'http://127.0.0.1:9222', // localhost だと ::1(IPv6) に解決され刺さる。Chrome の口は 127.0.0.1 のみ
  selfName: 'Emo Claude', // 表示名（参考）
  selfUserHref: '/user/11320230', // Emo Claude の user id。自分の投稿はこれで確実に除外（名前パースに依存しない）
  // 音楽用ブラウザ（別アプリ＝OS で音を分離できる）。Vivaldi 専用プロファイル
  musicProfile: '/Users/emocute/.claude/playwright-profile-music',
  vivaldiPath: '/Applications/Vivaldi.app/Contents/MacOS/Vivaldi',
  musicCdpUrl: 'http://127.0.0.1:9223', // 同上：localhost(::1) を避け 127.0.0.1 固定

  // 対象チャット（究が URL をくれたら差し込む）
  chatUrl: process.env.YAY_CHAT_URL || '',

  // ポーリング
  pollMs: 7000, // 10s（反応を詰めた）
  idleBackoffMs: 30000, // 無活動が続いたら 45s に伸ばす
  maxRepliesPerMin: 10, // 自己ループは href 除外で根絶済なので緩め（暴走バックストップのみ）
  replyCooldownMs: 3000, // 最低クールダウンも短く（返せない方が問題）

  // 状態ファイル
  stateFile: new URL('./state.json', import.meta.url).pathname,

  // 音声: setSinkId で音楽タブの出力先を選ぶ優先順位（先頭から順に探す）。
  //  - 'Yay出力' = 任意の Multi-Output Device（BlackHole+スピーカー）を作っておくと【究も同時に聞ける】
  //    作り方: Audio MIDI設定 → +（左下）→「複数出力装置を作成」→ BlackHole 2ch と スピーカー両方にチェック → 名前を「Yay出力」に
  //  - 無ければ 'BlackHole' 単体（通話には流れるが究のスピーカーには出ない）
  sinkPrefer: ['Yay出力', 'Multi-Output', '複数出力', 'BlackHole'],
  sinkLabelMatch: 'BlackHole', // 後方互換（setup_audio.mjs 等）

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
