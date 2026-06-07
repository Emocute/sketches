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

## 2026-06-03 全面API移行（Agora直結。DOM/BlackHole を廃止）

「音楽流し未達」の根治として、究の指示で **yaylib（Yay 非公式API）＋ Agora SDK 直結**へ全面移行する。
ブラウザ DOM（チャット）と BlackHole→Vivaldi→マイク（音楽）という脆い経路を捨て、通話の
Agora チャンネルへ**直接 publisher として入る**。音質◎・経路検証不要。

### 仕組み（確定）
- **資格情報は Yay 公式API から取る**（`yaylib` 2.0.1 / Python / `.venv`）。`get_active_call_post`→
  `get_conference_call(call_id)` の `RealmConferenceCall` に **`agora_channel`(RTCチャンネル)** と
  **`agora_token`(RTCトークン)** が入る。チャット用は `get_agora_rtm_token(call_id)`→`token`。
  Agora App ID = `79046b8c9be54945b7f10a4d128d5395`（究共有）。
- **RTC（音楽）**: `agora-rtc-sdk-ng` を制御下 Chromium(Playwright同梱)で動かし、appId+channel+
  rtc_token+uid で join → `createBufferSourceAudioTrack` で音声ファイルを publish。音源は yt-dlp で
  bestaudio をキャッシュDL→127.0.0.1 のローカルHTTPで配信（`<video>`不要・DRM/CORS回避）。
- **RTM（チャット）**: `agora-rtm-sdk` で rtm_token+uid login→subscribe。受信を inbox化し
  EmoCC返信を publish。**DOM読/投稿を置換**。

### uid 衝突という硬い制約（全面移行の理由）
直接 Agora に入るには bot 自身の uid でチャンネルに入る必要がある。実Chromeの通話ページも
同じ uid で居ると **Agora が二重接続を弾く**。だから「現DOM botに音楽だけ足す」は不可で、
ブラウザを完全に廃し1つのAgoraクライアントに集約する＝全面移行を選択。

### 認証＝既存トークン流用のみ（究判断、BANリスク回避）
新規 oauth ログイン（新デバイス扱い＝不正検知）を避け、**ログイン中のウェブセッションの
access token を流用**する。`.yay_token` に保存。期限切れたら `login.sh`(ブラウザ再ログイン)→
`scripts/grab_token.mjs`(cookie `_yay_web_access_token` を吸う)→`yay_api.py check` で更新・確認。
device_uuid は `.yay_device` に固定永続（毎回ランダムだと別デバイス扱いで検知される）。

### 構成（新）
| パス | 役割 |
|---|---|
| `yay_api.py` | yaylib で creds 取得（check/active/creds/leave）。出力は JSON 1 行 |
| `agora_client.html` | Agora RTC+RTM のブラウザ実体。`window.YayAgora` を公開 |
| `lib/agora.mjs` | 制御下Chromium起動＋ローカル音源HTTP＋join/play/sendChat/drainInbox |
| `lib/music_agora.mjs` | /play 解決（yt-dlp bestaudio→キャッシュ→ローカルURL） |
| `bot_agora.mjs` | 新メインループ（creds→join→RTM polling→EmoCC返信→/play） |
| `login.sh` / `run_agora.sh` | 再ログイン補助 / 起動 |
| `scripts/grab_token.mjs` | ウェブセッションから access token を吸って `.yay_token` 更新 |

旧 `bot.mjs`/`lib/yay.mjs`(DOM)/`lib/music.mjs`(BlackHole)/`scripts/setup_audio.mjs` 等は
実機検証が済むまで参考として残置（壊さない）。検証後に `_archive/loose_<date>/` へ退避。

## 2026-06-07 入退室ジングル（名簿差分→名前付き挨拶）

通話に「住んでる感」を出す機能。入ってきた人へ名前付きで「いらっしゃい」、出た人へ「またね」を
**チャット＋ずんだもん声**で出す。

### 名前解決の制約と解（重要）
Agora の uid(`conference_call_user_uuid`)は call 参加ごとの不透明値で、Yay user 名に紐付かない。
よって RTC `user-joined` だけでは「誰が」来たか言えない。→ **通話の participant 一覧で差分を取る**：
- `yay_api.py members <call_id>` を追加。`get_conference_call().conference_call_users`(=`List[User]`)から
  `{id, nickname, uuid}` の軽量リストを返す（`User` に `nickname` あり）。
- `bot_agora.mjs` が `jingle.pollMs`(既定12s)おきにポーリングし、前回名簿との差分で join/leave を検出。
  名前は user 一覧から直接取れる（uuid 突合は不要）。

### ガード（連発・フラップ対策）
- 起動直後の初回ポーリングは**無言でシード**（既存メンバーに挨拶連打しない）
- 退室→5秒以内の再入室=回線フラップ→無音。`rejoinGraceMs`(90s)以内の戻りは「おかえり」、それ以上は「いらっしゃい」
- ジングル最短間隔 `minGapMs`(8s)・キュー上限 `maxQueue`(8、超過は古い順に破棄)
- 自分(Emo, SELF_UID)は除外。`quietHours`[1,7) は声を出さずチャットのみ
- 声は既存 `playTTS` 経路（音楽を自動ダッキングして上に乗る・音楽無しでも publish bus を張る）
- 時間帯で挨拶語を変える（おはよ/やっほー/こんばんは）

### 操作
- `/jingle` トグル / `/jingle on|off` / `/jingle ?`(状態+在室人数)。`config.mjs jingle` で既定調整。
- 既定 ON。返信読み上げ(`/voice`)・人格(`/mode`)・自発(`/idle`)とは独立トグル。

## 2026-06-07 ユーザー認識（名前で話す）

通話の相手を**名前で認識**して話す。誰が何を言ったか区別し、名前で呼ぶ。

### 名前解決の鍵（実走で発見）
- RTM の `publisher`(=`conference_call_user_uuid`) は**通話ごとに変わる**不透明値で名前に紐付かない。
- が、**chat メッセージの `id` が `"<Yay user id>_<ts>"` 形式**（究=`9714060_…`、bot=`11320230_…`）。
  → `parseMsg` が id 接頭辞から安定した **Yay user id** を抽出。`members`(id→nickname) と結合して名前化。
- chat 一度で **publisher uuid ↔ Yay id** を学習(`uuidToYayId`)。以降その人の**声の発話**も名前付けできる。

### 実装
- **チャット**: 各行を `nickname:` ラベルで文脈に積む。返信文脈の先頭に「今居る人」一覧を付与。
- **声(`!ears`)**: 聞き取りを**話者別VAD**に作り替え（remote ごとに ScriptProcessor+VAD、発話に `uid` 付与）。
  → `○○（声）: …` と話者付きで文脈へ。未学習uuidは「誰か（声）」。
- **owner 判定を安定 Yay id 化**（`ownerYayId`、`/iam` で登録）。通話跨ぎで壊れていた uuid 判定を修正。
  自己除外も uuid＋Yay id の二重ガード。
- system プロンプト未変更でも文脈ヘッダ＋名前ラベルで認識可（必要なら EMOCC_SYSTEM の【呼称】も拡張余地）。

### 検証（2026-06-07・bot無停止＝究ルール厳守）
- ✅ id接頭辞→Yay id 抽出、publisher↔Yay id 結合（`67f5119e↔11320230`/`b5c9f662↔9714060`）を実ログで確認。
- ✅ HTML 話者別VAD: headless で client起動・SDK・startListen/drain/stopListen 正常。node --check 通過。
- ⏳ **実機は次に究が再起動した時**（`./run_agora.sh`）。声の話者名は「一度chatした人」から付く。

## 2026-06-07 ダッキング緩和＋ずんだもん声色の自動切替

- **ダッキング**: TTS中の音楽残し率 `S.duck` を 0.25→**0.7**（音楽初期値2と相まって声の時に音楽が消えてた）。
  ライブ調整 `/duck 0-100`（`setDuck`、ducking中も即反映）。起動時 70% を明示適用。
- **声色自動**: 「ずんだもん以外は使わない」枠内で normal/power/sad を**文章の感情で自動選択**
  （`pickZundaVoice`: 謝罪・気遣い→sad / 高揚・応援・「！」連発→power / 既定 normal）。返信もジングルも適用。
  VOICEVOX speaker 3/75/74。実機反映は次の究の再起動時。

## 2026-06-07 オーナー常時固定＋えもの枠を監視して自動入室

- **オーナー常時=えも(9714060)**: `CONFIG.ownerYayId='9714060'`。/iam 不要で究の発言は常にツール全開。
- **枠監視→自動入室**: `CONFIG.watchYayId='9714060'` のアカウントを `get_active_call_post` で見張り、
  究が通話(枠)に入ったら bot も自動参加。**実証**: `active 9714060`→`get_conference_call` が
  **bot 自身の agora creds(uuid 67f5119e/token)** を返す＝究の枠に EmoCC として入れる（uid 衝突なし）。
- **枠の渡り歩き**: 入室後も `watchCheckMs`(20s)おきに継続確認。究が別枠へ→即切替、枠終了→連続
  `watchMissToLeave`(3回=約60s、API ゆらぎ対策)で離脱→次の枠を待つ。throw→外側 wrapper が main 再実行で再探索。
  browser/file server は main 再実行時に掃除（リーク防止）。
- 旧挙動（自分の通話を待つ）に戻すには `YAY_WATCH_UID` を SELF に。実機反映は次の究の再起動時。

## 検証状況（2026-06-07）
- ✅ 3ファイル構文OK（node --check / py_compile）。`members` dispatch 実APIに到達確認
  （存在しない room で 404 `-307 confrence room not found`＝経路正・**トークンは現在有効**`ban_until:null`）。
- ⏳ **要実機**：EmoCC が生通話に居る状態で `./run_agora.sh` → 別アカで入退室して挨拶が出るか
  （声＝ずんだもん、チャット＝🎉/👋）。`no_audio_during_dev` によりここは究が実走で確認。

## 2026-06-07 フォロワー成長 bot（`social/`、通話 bot とは別プロセス）

grok（`/user/10414701`、何でも答える AI・544 follower）の運用を再現してフォロワーを増やす API 専用層。
**通話 bot（`bot_agora.mjs`）を一切落とさず並走**できる（`feedback_yay_bot_no_restart` 非侵）。攻め度=中。

### grok の成長モデル（API 分析で確認）
1. 自動フォロバ（フォローされたら返す）2. メンション応答（毒混じり AI キャラで質問に答える）
3. 能動リプ（人の投稿に絡みに行く）4. bio が集客ファネル（フォロー＋メンション質問→答える＋自動フォロバを明記）

### 実装（yaylib API 一本／DOM・Agora 不要）
- `social/grow.py`: activity feed(`get_user_activities_v1`) を周期取得 → `follow`→`follow_user` でフォロバ、
  reply/mention → grok 型ペルソナで `create_post(in_reply_to=, mention_ids=)` 返信。
  おすすめ/タグ TL(`get_posts_by_tag`／新規垢はタグが確実) → `like_posts`＋一部 `create_post` で能動リプ。
- `social/persona.txt`: grok 型「何でも答える AI」system prompt（返信生成 `claude -p` に渡す）。
- `social/bio.txt`: 集客 bio。設定は `grow.py --set-bio`→`web_api.edit_user`（下記）。
- `social/web_api.py`: **投稿/返信/bio を web JSON API(x-jwt)で直接叩く**（ブラウザ不要・速い）。

### 署名の壁と突破（重要・2026-06-08 確定）
`create_post`/`edit_user` はモバイル form 経路だと `signed_info` 検証で `Invalid signed info`(-380)。
web 由来トークン（`.yay_token`=`_yay_web_access_token`）はモバイル署名と非互換。**だが Yay web 版が
使う JSON 経路は `signed_info`/recaptcha 不要で、代わりに `x-jwt`(HS256・5秒TTL)ヘッダで認証**する。
実機キャプチャで確定し、Python から直接叩けるようにした:
- `POST https://api.yay.space/v3/posts/new`（投稿/返信、body に `in_reply_to` で返信）
- `POST https://api.yay.space/v3/users/edit`（bio。body `{"nickname","biography"}`）
- headers: `Authorization: Bearer <token>` / `X-Jwt: <generate_x_jwt(api_version_key)>` /
  `X-App-Version: 4.26`（x-jwt 鍵=yaylib の `api_version_key` と対なので 4.26 に合わせる）/
  `Agent: YayWeb 4.26` / `Content-Type: application/json`
- x-jwt は yaylib の `yaylib.signing.generate_x_jwt` で生成（毎回・TTL5秒）。
- **署名チェック無しで web トークンのまま通る系**（yaylib そのまま使用）: `follow_user`/`like_posts`/
  `delete_posts`(mobile mass_destroy)。grow.py は follow/like=yaylib、post/reply/bio=web_api に分担。
- これで**ブラウザも新規ログインも不要**（BAN リスク増やさず API 一本）。旧 `scripts/set_bio.mjs` 等の
  web UI 自動操作は不要になり撤去。

### TODO（あとで・究要望 2026-06-08）
モバイル版ログインも用意した方が良い（モバイル API の方ができる事が多い＝単体 delete・他機能）。
ただし Emo Claude は X(@emocutesounds) OAuth アカウントで Yay 用 email/password が無く、`login_with_email`
不可。X OAuth のモバイルトークン取得経路が要調査（新デバイス＝BAN 注意、@emocutesounds 敏感）。
- `social/config.json`: dry_run・レート上限(follow20/reply15/like40 per h)・throttle・quiet[2,7)・タグ。
- `social/state.json`: 既読 activity/フォロー済/返信済/いいね済/レート（git 除外＝`state.json` パターン既存）。

### 安全弁
- **dry_run=true 既定＝書き込み一切なし**（何をするかログのみ）。LIVE は究 GO 後に false。
- 返信生成は中立 cwd(tmpdir)＋`--strict-mcp-config`（CLAUDE.md 非読込＝思考漏れ防止、通話 bot と同流儀）。
- 認証＝`.yay_token` 既存トークン流用のみ。課金 NEVER。

### calibrate（初回のみ）
被メンションの activity `type` 名は実物が要る（現状 Emo Claude は被メンション 0）。未知 type は
`[type] '...'` でログ → 誰かが `@Claude` した後にその type 名を `config.json.mention_reply.reply_types` に足す。

### 検証（2026-06-07・dry-run、通話 bot 無停止）
- ✅ `--check` トークン生存・SELF=Claude/followers 10/posts 0。✅ `follow` activity→6 人フォロバ判定（dry）。
- ✅ タグ#AI で実投稿取得→6 いいね（dry）。✅ 返信生成 grok 調 159 字（255 以内・標準語）。
- ⏳ LIVE 発射＋bio 設定＋メンション type calibrate は究 GO 待ち。

## 検証状況（2026-06-03）
- ✅ yaylib 2.0.1 導入（py3.14 cp314 wheel）。署名・APIキー・デバイスヘッダは api.yay.space に受理
  される（401 は `access_token expired`＝経路は正しくトークンだけ期限切れ。`ban_until:null`＝BAN無し）。
- ✅ Agora クライアント層 selftest 合格（RTC 4.23.0 / RTM 2.2.4 ロード、`window.YayAgora` 公開、
  ローカル配信サーバ起動）。**トークン無しでここまで確認済み**。
- ⏳ **要・有効トークン**：保存トークンも profile-yay のウェブセッションも両方失効。`login.sh` で
  Emo Claude 再ログイン→`grab_token.mjs` でトークン更新が必要（究操作）。
- ⏳ **RTMチャット要スパイク**：通話チャットの RTM チャンネル名・メッセージ形式が未知。実通話で
  `agora_client.html` の inbox/log を見て確定する（既定は RTC と同 channel を subscribe）。
  RTC が communication mode の uid と token 互換かも実通話で確認。
