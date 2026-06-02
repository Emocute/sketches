# yay_bot

## 目的

Yay（yay.space）のグループチャットに EmoCC 人格の Claude を常駐させ、会話に反応しつつ、別ブラウザで YouTube/Spotify の音楽を再生して Yay 通話に流す（DJ的）。

## 技術スタック

- **トランスポート**: Playwright（実 Chrome + 専用永続プロファイル `~/.claude/playwright-profile-yay`）。Yay は公開 API なし → ブラウザ自動操作のみ。初回ログインのみ手動。
- **頭脳**: Claude-in-the-loop（tmux、15–30s ポーリング / 全メッセージ反応 / EmoCC 人格）。
- **音楽**: 別ブラウザ（Vivaldi 専用プロファイル）で YouTube + Spotify(Premium)。`setSinkId` で音楽タブの音を BlackHole 2ch に出力 → Yay 通話のマイク入力 = BlackHole で部屋へ。
- **音声経路**: BlackHole 2ch（無料・導入済）。Multi-Output（ローカル試聴）は任意で後付け。

## 最小スコープ（v1 簡易版）

1. profile-yay で Yay ログイン状態を維持、対象チャットを開く
2. チャットの新着を差分検出（最終既読を状態ファイル保持）
3. EmoCC で返信生成 → 投稿（連投ガード）
4. 「/play <曲>」等で音楽ブラウザに再生指示 → BlackHole 経路で通話へ

## ガード

- 課金 NEVER（Spotify Premium は既契約、新規購入は GO 待ち）
- 開発・検証中は音を自動発火させない（再生確認は究）
- 投稿前フィルタ（不利情報非開示・身内表現除去）
- Yay 自動操作の ToS は自アカウント・低頻度で運用

## チャット取得方式の調査結論（2026-06-01・重要）

通話内チャットは **Agora RTM（暗号化バイナリのデータチャンネル）**に載っている。検証で確定：
- REST API（`api.yay.space/v1`）には heartbeat（`/users/alive`）しか出ない
- `wss://cable.yay.space`（Rails ActionCable）はアプリ通知用で、通話チャットは流れない
- チャット送信時に出るのは全部 Agora ws の binary フレーム（204B 等）
→ **API/websocket 直叩きは構造的に不可能**（Agora SDK の独自バイナリ署名プロトコル）。
→ **DOM 経由（Playwright + CDP 接続）が唯一の現実解**。これは妥協ではなく制約。

### DOM セレクタ（実画面で較正済み・config.mjs に反映）
- 通話画面 `/conference/<id>`、チャット開く `.ConferenceCallScreen__toolbar__item--chat`
- 行 `.Messages__item` / 本文 `.Messages__item__span--text` / 送信者 `.Messages__item__img img[alt="〇〇のカバー写真"]` / href `/user/<id>`
- 入力 `textarea.CallChatReplyForm__form__input` / 送信 `button.Button--icon-chat-send`
- 通話マイク選択は「通話音声設定」(`.ConferenceCallScreen__sound_management`)内の `<select>`（BlackHole 2ch を選べる）
- 自分(Emo Claude)= `/user/11320230`。自己投稿は href で除外（名前パース不可な時がある）

### 重要な実装上の注意
- `claude -p` は**中立ディレクトリ(os.tmpdir)で叩く**。リポジトリ内で叩くと巨大 CLAUDE.md を読み「思考」を垂れ流す
- Chrome/Vivaldi は**デバッグ口付きで起動→connectOverCDP**（launchPersistentContext はロック衝突）
- リロードは通話から落ちる＋マイク設定リセットなので避ける

## 状態

- 2026-06-01 起票。BlackHole 導入済、Claude アバター取得済、profile-yay 作成済、DOM bot 稼働（自己ループ/思考漏れ/パネル閉鎖の各バグ修正済）。
- 音楽 DJ：Vivaldi(9223)+Spotify ログイン済、setSinkId→BlackHole 検証OK。ただし sniff 用リロードで通話マイクがミュート＋BlackHole 選択リセット済（再設定が必要）。

### 2026-06-02 音声経路の作り直し（「音楽が通話に流れない」の根治）
原因は実装の脆さ。潰した点：
1. **CDP の `localhost` が IPv6 `::1` に解決され接続が刺さってた** → CDP URL を `127.0.0.1` 固定＋launcher に `--remote-debugging-address=127.0.0.1`。bot の音楽接続不安定の元凶。
2. **再生ページとルーティング先がコンテキスト跨ぎでズレ得た** → connectMusic/connectYay/diag を全コンテキスト走査に。
3. **`/play` 既定が Spotify Web（Widevine DRM で setSinkId 不適用）** → **YouTube 既定**化（`/sp` で明示 Spotify）。
4. **通話マイク=BlackHole の手設定依存** → `/play` 時に bot が `ensureCallAudio` で自動保証（マイク選択＋ミュート解除）。
5. **経路検証ゼロ** → routeToBlackHole が setSinkId 適用・再生進行を検証。`scripts/diag_audio.mjs` で全リンク ✓/✗ 点検。
6. **`--use-fake-ui-for-media-stream` が Chromium を遅延クラッシュさせてた** → 除去し `ctx.grantPermissions(['microphone'])` で代替。起動先 `about:blank`。
7. **音楽ブラウザは Yay と別アプリ(Vivaldi)必須**：Chrome 2インスタンスは macOS シングルトンで後発(9223)即死。
- **未解決(環境依存)**：背景(サンドボックス)実行だと2つ目のGUIブラウザ(9223)が数十秒で回収される事象あり。究の実ターミナルで `./run.sh` を叩く実セッションでは出ない見込み（要実機確認）。
- 究も同時試聴したい：Audio MIDI設定で複数出力装置(BlackHole＋スピーカー)を「Yay出力」と命名 → `config.mjs sinkPrefer` が自動優先。
