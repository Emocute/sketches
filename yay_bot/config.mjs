// yay_bot 設定
export const CONFIG = {
  // 専用プロファイル（実 Chrome）。窓はデバッグ口付きで起動し CDP 接続する
  yayProfile: '/Users/emocute/.claude/playwright-profile-yay',
  cdpUrl: 'http://127.0.0.1:9222', // localhost だと ::1(IPv6) に解決され刺さる。Chrome の口は 127.0.0.1 のみ
  selfName: 'Emo Claude', // 表示名（参考）
  selfUserHref: '/user/11320230', // Emo Claude の user id。自分の投稿はこれで確実に除外（名前パースに依存しない）

  // ── オーナー＆監視（2026-06-07 究指示）──
  //   究のアカウント = えも（Yay user id 9714060）。常にオーナー（/iam 不要）。
  //   watchYayId のアカウントを見張り、そのアカウントが通話(枠)に入ったら bot も自動参加する。
  //   仕組み: get_active_call_post(watchYayId) で枠を発見 → get_conference_call で bot 自身の
  //   agora creds(uuid/token) が出る（実証済）→ Agora 直結。枠が終わったら離脱して次の枠を待つ。
  ownerYayId: '9714060',   // 究=えも。常時オーナー（YAY_OWNER_YAYID / state で上書き可）
  watchYayId: '9714060',   // 監視対象=えも。YAY_WATCH_UID で上書き可。SELF にすると自分の通話を待つ旧挙動
  watchCheckMs: 20000,     // 監視通話の継続確認の間隔
  watchMissToLeave: 3,     // 連続この回数「枠なし」を見たら離脱（API のゆらぎ対策）
  // ── 機能フラグ ──
  // Spotify Web Player 自動操作（BlackHole 経路）。Premium 契約 + Vivaldi 要。
  // false にするとすべての Spotify 再生パスが無効化され YouTube のみになる。
  spotifyEnabled: false,

  // 音楽用ブラウザ（別アプリ＝OS で音を分離できる）。Vivaldi 専用プロファイル
  musicProfile: '/Users/emocute/.claude/playwright-profile-music',
  vivaldiPath: '/Applications/Vivaldi.app/Contents/MacOS/Vivaldi',
  musicCdpUrl: 'http://127.0.0.1:9223', // 同上：localhost(::1) を避け 127.0.0.1 固定

  // 対象チャット（究が URL をくれたら差し込む）
  chatUrl: process.env.YAY_CHAT_URL || '',

  // ポーリング（応答高速化 2026-06-06: メッセージ/コマンド取得の待ちを詰めた）
  pollMs: 2500, // 受信ポーリング間隔。コマンド体感を速く（CDP drainInbox は軽い）
  idleBackoffMs: 30000, // 無活動が続いたら伸ばす
  maxRepliesPerMin: 10, // 自己ループは href 除外で根絶済なので緩め（暴走バックストップのみ）
  replyCooldownMs: 2000, // 最低クールダウン（返せない方が問題なので短め）

  // ── 入退室ジングル（参加者名簿の差分→挨拶。チャット＋ずんだもん声）──
  //   名前は通話の participant 一覧(Yay user)から取る（Agora の uuid は名前に紐付かないため）。
  //   声は既存の playTTS 経路（音楽を自動ダッキングして上に乗る）。/jingle で実行時 ON/OFF。
  jingle: {
    enabled: true,        // 既定ON（/jingle off で止める）
    pollMs: 12000,        // 名簿ポーリング間隔（python spawn なので控えめ）
    rejoinGraceMs: 90000, // 退室→この時間内の再入室は「おかえり」、5秒以内の瞬断は無音（フラップ抑制）
    minGapMs: 8000,       // ジングル最短間隔（同時入室の連発抑制。1件ずつ捌く）
    voice: true,          // 声を出す（false ならチャット挨拶のみ）
    quietHours: [1, 7],   // [開始時,終了時) この帯は声を出さずチャットのみ（深夜配慮）。null で無効
    maxQueue: 8,          // 溜まり過ぎ防止（超えたら古いものから捨てる）
  },

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
