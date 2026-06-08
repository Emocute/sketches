# yay_bot SESSION_LOG

時系列の作業記録。詳細設計は `CONCEPT.md`、引き継ぎは `_drafts/HANDOFF_*.md`。

---

## 2026-06-08 — コマンド最優先化＋本名マスク＋音楽ぶつぶつ解消（3件）

**Session UUID**: e748fed5-9ab6-4787-8628-2303bf2f3e5e

### 背景（究の3要望）
1. `/ears`（聞き取り）を入れるとチャット/コマンドが効かなくなる → コマンドが何より最優先で常時応答してほしい。
2. bot が究の本名を読み上げ/表示するのをやめたい（恒久）。
3. bot が流す音楽がぶつぶつする（再起動後）→ ならないように。

### 1. コマンド・チャット最優先化（bot_agora.mjs、commit 77f98b6）
- 原因: メインループが聞き取り whisper（最大30s）＋返信 LLM を `await` で順次処理 → ループ下部のチャット/コマンド処理に到達できず操作が止まる。
- 修正: `bgBusy` 単一実行ガード＋`runBg()` を追加し、**聞き取り whisper・会話返信 LLM・自発おしゃべり LLM** を非同期 background 化。メインループは毎tick「チャット受信→コマンド同期処理」を必ず実行＝コマンド最優先。重い処理は同時1本。
- 仕様メモ: 背景処理中に来た**会話**は次tickへ送られる（文脈には積まれる）。コマンドは常時即応。

### 2. 本名の恒久マスク（config.mjs + bot_agora.mjs、commit f006f9c）
- 原因: Yay の `nickname` が本名で、入退室あいさつ（チャット＋ずんだもん声）・会話文脈ヘッダ・声の話者名・presentNames の全経路に出ていた。
- 修正: `config.nameAlias = { '9714060': 'えも' }` を追加し、表示名解決を単一の `aliasNick()` に集約。究（Yay id 9714060）は常に「えも」表示＝本名は LLM 文脈にも TTS にも一切渡らない。別名変更は config 1箇所。

### 3. 音楽ぶつぶつ＝バッファ枯渇の解消（lib/agora.mjs・bot_agora.mjs・lib/listen.mjs、commit 71bdcf6）
- 構成: 音楽は headless Chrome 内 `<audio>` プログレッシブ再生を node プロキシ（`/stream`→googlevideo）で給餌し、リアルタイムで Agora に publish。node の event loop が詰まると即バッファ枯渇＝ぶつぶつ。
- **主因**: `/stream` プロキシが背圧無視で `res.write` 垂れ流し → 数十MBのトラックが node メモリに溜まり GC で event loop が詰まる。→ `stream.pipeline` 化（消費ペースで上流読取を止め、メモリ一定・切断で上流中断）。
- 併せて: 録音追記を同期 `appendFileSync`→非同期 `appendFile` ／ 録音 drain を毎周回→6s間引き（`YAY_REC_DRAIN_MS`）／ 停止・スナップの mp3 変換を同期`execFileSync`→非同期（通話切替時の数秒フリーズ除去）／ whisper スレッド 4→2 既定（`YAY_WHISPER_THREADS`）。

### 4. 入退室あいさつの深夜配慮を無効化（config.mjs、commit 613c95e）
- 症状: 「入った人に声で読み上げなくなった」。原因はバグでなく config `quietHours: [1, 7]`（1〜7時は声オフ・チャットのみ）。実時刻 01:56 で帯内に入り声だけ抑制されていた（あいさつ自体はチャットに出ていた）。
- 修正: 究指示で `quietHours: null`＝24時間声あり。夜静かにしたい時は `[1,7]` 等に戻すだけ。

### 運用
- 通話中ホット再起動を複数回（`./run_agora.sh`）。毎回 RTC/RTM クリーン接続・自動枠参加・録音開始を確認。途中 RTM未参加で枠を見失う事象あり→再起動で復帰。最後は「通話待ち受け」状態で終了（究が枠に入れば自動参加）。
- 全コミット `Emocute/sketches` main、Claude author、push 済（77f98b6 → f006f9c → 71bdcf6 → 613c95e）。
- 未検証: 音楽ぶつぶつの実聴改善は究の確認待ち。残るようなら音量帯・特定曲を切り分け。

---

## 2026-06-08 — 操作コマンド受付トグル /cmds 追加（オーナー専用・state永続）

**Session UUID**: 00a32cc2-7074-4169-8911-e8fc62cf578f

### 背景
- bot を落とさずに `/play` 等の操作コマンド応答を一括 ON/OFF したい（究要望）。既存トグルは jingle/ears/voice/idle 等の個別のみで、操作コマンド全体のマスタースイッチが無かった。

### 仕様（究判断）
- 無効化の範囲＝**操作コマンドのみ**（`/play` 等）。会話返信・音楽再生・入退室あいさつは継続。
- 切替権限＝**オーナーのみ**（`/iam` 登録者）。OFF中でも `/cmds on` だけは常に効く（復帰経路を塞がない）。

### 実装（bot_agora.mjs、7箇所）
- グローバル `let cmdsEnabled = true;`
- `CMD.cmds = ['cmds','commands','cmd','コマンド']`
- `handleCommand` 先頭にゲート: `cmd==='cmds'` ならオーナー判定して on/off/toggle/?（OFF中もここだけ通す）。それ以外は `!cmdsEnabled` で `return null`（＝コマンド黙殺、会話・音楽は別経路で継続）。
- `persistFlags()`（seen を壊さずマージ書き込み）／state load で `cmdsEnabled = st0.cmdsEnabled !== false`（既定ON・継承）／メインループ saveState に `cmdsEnabled` 追加。
- `statusBlock()` と `renderHelpFull()` に表示行追加。
- 構文チェック OK、commit `8dd12f6`（Claude author）+ push。

### 運用メモ
- 使い方: `/cmds off`｜`/cmds on`｜`/cmds`（トグル）｜`/cmds ?`（状態）。
- 通話中ホット再起動を2回実施し新コード反映。RTC/RTM クリーン接続を確認。
- 既知の残課題: チャット送信が稀に `RTM -10025（service not connected）`。ボイス挨拶は正常。RTM 瞬断、未修正。

---

## 2026-06-04 — キュー一覧/ヘルプが効かない不具合を修正（コマンドを連投ガードから除外）

**Session UUID**: E59B8570-2171-4410-8D0F-216488A3F682

### 症状（究報告）
- 「キューリストが機能してない」「できることとヘルプが繋がってない」。

### 根本原因（両症状とも同一）
- メインループのコマンド処理が `if (mr && canReply()) { send }` になっており、**明示コマンドの応答を連投ガード（クールダウン＋毎分上限）が握り潰していた**。bot が直前に会話返信していると `/q`（一覧）`/h`（ヘルプ）`/st` `/qd` 等を打っても応答が送られず「効かない」に見えた。
- 副因（内容面）: 簡易ヘルプ `/?` がキュー操作コマンド（`/q`一覧・`/qd`/`/qu`/`/qj`）を載せておらず、できることとヘルプが食い違っていた。

### 直し
- `bot_agora.mjs`: コマンド応答を `canReply()` から除外し**常に返す**（連投ガードは会話返信・自発おしゃべりだけに掛ける。コマンドは究の明示要求＝決定論ローカル応答でフラッド源にならない）。`markReplied()` も呼ばない（会話バジェットを消費しない／コマンドは `conv` から除外済で二重返信もしない）。
- `renderHelpShort`: キュー操作（`/q` 一覧/追加・`/qd`/`/qu`/`/qj`・`/c`）を明記し詳細ヘルプと整合。

### 検証
- `node --check` OK、`renderQueue`/`handleCommand`/ヘルプ系の重複定義なし。実通話での挙動確認は究（俺からは音を出さない）。

---

## 2026-06-04 — ミックスバス修正のコミット締め＋壊れたHEADの整合（並行セッション収束）

**Session UUID**: E59B8570-2171-4410-8D0F-216488A3F682

### 背景
- 「Yay bot 開発続行」で引き継ぎ最優先（HANDOFF§既知バグ#1）の **読み上げ中BGM消失**を WebAudio ミックスバスで修正（実装内容は直下 3931190a 枠と同一）。
- 着手後に**別セッション(3931190a)が並行して同一修正**をしていたと判明（SESSION_LOG が編集中に変化）。幸いディスク上のコード3ファイルは単一定義でクリーン（関数重複なし・JS構文OK・ヘッドレススモークで `playTTS` 公開＋`MediaStreamDestination`→`createCustomAudioTrack` の核経路 track=live を確認）。

### やったこと（究GO「コミットして締める」）
- working tree のミックスバス修正をコミット（fix）: `agora_client.html`/`lib/agora.mjs`/`bot_agora.mjs`。
- **壊れたHEADの整合**: コミット済 `bot_agora.mjs` が `./lib/listen.mjs` を import しているのに `listen.mjs` 等が未追跡＝fresh checkout で壊れる状態だった。前セッションの音声機能未追跡ファイル（`lib/listen.mjs`/`scripts/voicevox_engine.sh`/`scripts/create_multiout.swift`/`_drafts/HANDOFF_2026-06-04.md`）を追跡化（feat）。

### 残（実機確認・俺からは音を出さない＝no_audio_during_dev）
- 生通話にEmoCCが入った状態で `./run_agora.sh`→音楽再生中に `/voice` ONで読み上げが乗り、BGMがダッキング後に復帰するか実通話で確認。クリーン再起動はHANDOFF§手順。

---

## 2026-06-04 — TTS×音楽を WebAudio ミックスバス1本化（読み上げ中もBGMが消えない）

**Session UUID**: 3931190a-47d0-4e0a-9248-76bcfb4f5582

### 背景
- 引き継ぎ「Yay bot 開発続行」。旧実装は TTS を別トラックで publish しており、読み上げのたびに音楽トラックが置換され **BGM が消える**問題があった（HANDOFF §「TTSはこの経路依存をやめ Agora直publish化済（が下記バグ）」の解消）。

### やったこと
- `agora_client.html` に **WebAudio ミックスバス**を導入。`musicGain`＋`ttsGain` → 単一の `MediaStreamDestination` → Agora へ publish するトラックを **1本だけ**に統一（バスは常時 publish、無音時はサイレンス）。
  - 音楽: `createMediaElementSource`/`getUserMedia`(BlackHole 等) → `musicGain` に合流（全DLせず即流す real-time 経路は維持）。
  - 読み上げ: `playTTS(url)` で WAV を `ttsGain` に乗せ、再生中は `musicGain` を `duck` 率(既定0.25)まで下げ、終了で現在音量へ復帰 → **音楽を止めずに読み上げが乗る**。
  - 音量制御は `musicGain.gain`（`volToGain`、既定15）で行い、Agora `setVolume` には依存しない（バス自体は原音 setVolume(100)）。
- `lib/agora.mjs`: `playTTS` ラッパ export 追加、`leave()` でバス破棄。
- `bot_agora.mjs`: `sayOut` を `playUrl` → `playTTS` に切替（ダッキング経路を通す）＋詳細ログ。
- 旧参照（`S.musicTrack`/`publishLiveTrack`/`captureStream`）の残存チェック・JS 構文チェック実施。

### 着地物（未コミット＝working tree）
- `yay_bot/agora_client.html`（ミックスバス本体）/ `yay_bot/lib/agora.mjs`（playTTS export）/ `yay_bot/bot_agora.mjs`（sayOut 切替）
- 引き継ぎ下書き `yay_bot/_drafts/HANDOFF_2026-06-04.md`

### 残（実機確認）
- 生通話に EmoCC が入った状態で `./run_agora.sh` → 音楽再生中に `/voice` ON で読み上げが乗り、BGM がダッキング後に復帰するかを実通話で確認。

---

## 2026-06-04 — Session 枠ガード応答・終了フロー

**Session UUID**: 6541f253-6957-4ff7-9c5d-66bbba3a0ceb

### やったこと
- Hook feedback により SESSION_LOG 枠ガード要件を検出
- 現セッション UUID でセッション枠を SESSION_LOG 先頭に作成

### 着地物
- Session UUID 6541f253-6957-4ff7-9c5d-66bbba3a0ceb の枠をセッション終了時に作成

---

## 2026-06-04 22:35 JST — Session 枠ガード対応・終了フロー検証

**Session UUID**: df66d78d-2218-452a-ad9e-b81166ac4e05

### やったこと
- Hook feedback により SESSION_LOG.md の Session UUID 枠ガード要件を検出
- 現セッション UUID でセッション枠を作成

### 着地物
- Session UUID df66d78d-2218-452a-ad9e-b81166ac4e05 の枠を SESSION_LOG 先頭に作成

---

## 2026-06-04 — Yay bot 音声機能拡張（VOICEVOX/STT/ボイスパック）・孤児掃除

**Session UUID**: 831d8225-ef90-475f-a812-7b0444366e31

### やったこと
- **Spotify DJ 経路確立**: 「Yay出力」複数出力装置(CoreAudio stacked aggregate=BlackHole+Steinberg)を `scripts/create_multiout.swift` で作成、システム出力に設定。Spotify→BlackHole→bot `/lv` 取込→通話。
- **VOICEVOX エンジン導入**: arm64 headless engine(約2GB)を `.voicevox_engine/` に展開(gitignore)、`scripts/voicevox_engine.sh` で起動制御。ずんだもん(spk3)本声TTS。
- **読み上げ(TTS)**: `lib/tts.mjs`(VOICEVOX/say フォールバック・VOICE_PACKS)、`sayOut` で返信発話。`/voice` トグル。
- **聞き取り(STT)**: `lib/listen.mjs`(whisper.cpp/Metal、remote音声→VAD→文字起こし→返信)。`/ears` トグル。
- **人格**: zundamon/natsuki(辛辣)/succubus(妖艶)。`/mode` 切替。
- **再生UX**: 再生前に正式タイトル通知、未ヒット❌、キュー番号編集(`/qd /qu /qj`)、一曲ループ、`/h`詳細`/?`簡易ヘルプ、`/st`状態。
- **孤児掃除**: SAME_UID_LOGIN/UID_BANNED の原因= Chromium孤児6個/bot2個 を特定し pkill 掃除。クリーン再起動手順を確立。

### 着地物・申し送り
- 引き継ぎ正本 → **`_drafts/HANDOFF_2026-06-04.md`**（インフラ・機能・既知バグ・クリーン再起動手順・落とし穴）。
- **未完(優先順)**: ①読み上げでBGM消える(WebAudioミックス`playTTS`要・今回Edit落ちで未適用) ②人格/ボイス切替UI＋ずんだもんスタイル ③自発おしゃべりとZunda分離 ④シーク ⑤Botから任意送信 ⑥ヘルプ整形。
- **反省**: ツール呼び出しのタグ崩れで多数の編集が空振り・同作業を反復失敗。次回は1回ずつ確実に、動く前にprocess/tmux確認。

---

## 2026-06-04 xx:xx JST — 並行編集による競合検出・終了報告

**Session UUID**: 0be1a163-aba9-4d32-abc7-988922b5a412

### やったこと
- agora_client.html の playTTS（BGM ミックス）消失を grep で検出
- sayOut の上書きも確認（別物に置換）
- 別セッション並行編集による競合と判定
- SESSION_LOG に事実を記録

### 着地物
- agora_client.html の競合状況を SESSION_LOG に記録
- 復旧手順を提示（git log/git show での再適用）

---

## 2026-06-04 xx:xx JST — 終了フロー整合性検証

**Session UUID**: aa407a29-df65-4771-8c4d-8098e0b1c4d3

### やったこと
- bot_agora.mjs・lib/tts.mjs 構文検証
- プロセス確認（bot×2稼働、Chromium停止）
- SESSION_LOG 記入

### 着地物
- 構文チェック全OK（bot_agora.mjs・lib/tts.mjs）
- プロセス状態正常確認

---

## 2026-06-04 xx:xx JST — 終了フロー

**Session UUID**: c0c97861-7e92-4cdc-b0eb-618dfecdc3a0

### やったこと
- bot のJS構文チェック、プロセス、ログ確認で整合性を検証

### 着地物
- bot_agora.mjs: 構文OK / lib/tts.mjs: 構文OK / lib/claude.mjs: 構文OK / agora_client.html JS: 構文OK
- プロセス正常（bot 1, chromium 1）
- ログ末尾正常

---

## 2026-06-03 18:xx JST — 前セッション要約

**Session UUID**: b288df71-82d6-4346-81b7-f5316df1a55a

### 前セッション終了レポート圧縮
- セッション `a591a864-55d1-49c3-b272-3711ebbdaf4c` の終了内容（SessionUUID追記・commit pushによるsession_protocol準拠完成）を50字以内に要約。
- 要約文: 「SessionUUID追記をpushしsession_protocol準拠が完成した。」

---

## 2026-06-03 14:xx JST — RTMフォーマット確定・なりきり人格・自発おしゃべり・チャットトグル

**Session UUID**: a591a864-55d1-49c3-b272-3711ebbdaf4c

### RTM メッセージ形式を生通話で確定（SESSION_LOG「要発見」だった件）
- 受信生メッセージ = **`<type> <JSON>`**。チャットは `chat {"text":"...","created_at_seconds":<unix>,"id":"<yay_uid>_<ms>"}`。
- 旧 `parseMsg` は型プレフィックス(`chat `)を剥がせず: ①`/play`等が `/` 判定に当たらずコマンド未発火 ②本文がJSONごと残る。
  → `parseMsg` で `^(\w+)\s+([\[{]...)` で型を分離→JSON解析→`text` 抽出。`chat` 以外（presence等）は無視。dedup id は payload.id 優先。
- **送信も生テキストだとYayクライアントが表示できない**（究の画面に出ない原因）。`yayEnvelope()` で受信と同形 `chat {json}` に包んで publish（`sendYayChat`）。全送信経路を置換。

### なりきり人格（`lib/claude.mjs`）
- `PERSONAS.zundamon`（語尾「〜のだ」、一人称ぼく/ずんだもん）追加。`emoccReply(ctx,{system})` で system 差し替え可に。
- `idleChatter(ctx,{system})` 新設＝場が静かな時に自分から一言を生成。

### 自発おしゃべり（中スパン）
- 人格ON時のみ、直近活動から `IDLE_QUIET`(35s) 空き＋`IDLE_MIN〜MAX`(既定90〜150s)で独り言/話題振り。`YAY_IDLE_MIN/MAX/QUIET` で調整。
- ローリング会話履歴 `recentLines` を返信/独り言の文脈に共用。

### チャットからトグル（再起動不要）
- 人格を実行時変数化（`personaKey/personaSys`、idleスケジュールもモジュールスコープ）。
- コマンド: `/zunda`=ON/OFFトグル、`/mode zunda|off`=明示切替/通常復帰、`/mode`=現状表示。ON時は一発目を即発火。
- **既定OFF**（究が「ON」と言うまで人格は出さない方針）。`YAY_PERSONA=zundamon` で起動時ONも可。
- `/h` ヘルプを改行付き複数行に整形。

### 運用メモ
- 通話が落ちても bot は待ち受けに戻り、究が入り直すと自動再参加（実走で確認）。
- 停止はクリーン（今回 tmux kill 後の孤児Chromium 0）。残注意は下記「停止の注意」。

---

## 2026-06-03 13:xx JST — 音量制御・汎用コマンド一式（1-2文字エイリアス）・キュー・チャット合体

### 音量
- music 配信に音量制御。既定 **15**（究感覚で 0〜100、100=原音が爆音だった）。`YAY_MUSIC_VOL` で上書き、`/v 0-100` でライブ調整。
- Agora `setVolume`（custom track）。captureStream の `<audio>.volume` は publish 音量に効かないため track 側で制御。

### 汎用コマンド（`/` でも `!` でも、1〜2文字エイリアス対応）
- `/p 曲`=今すぐ /`/q 曲`=キュー追加 /`/s`=スキップ /`/x`=停止(キュー消) /`/ps`=一時停止 /`/r`=再開
  /`/v 0-100`=音量 /`/np`=再生中+キュー /`/l`=ループ /`/lv`=システム音声 /`/d`=入力一覧 /`/c`=キュー消去
  /`/pi`=ping /`/bye`=通話離脱 /`/h`=help。エイリアス表は `bot_agora.mjs CMD`。
- **キュー自動送り**: 曲が終わると（page status の nowPlaying=null 検知）次の曲を自動再生。

### チャット合体（既存 EmoCC）
- EmoCC の脳（`lib/claude.mjs emoccReply`）は新 bot が既に使用＝チャット返信と音楽DJが1本(`bot_agora.mjs`)に統合済み。
  旧 `bot.mjs`（DOM/BlackHole）は参考に残置。

### 同一アカウント衝突（未解決の設計課題）
- bot は EmoCC(11320230) 自身で入るので、究が同じ EmoCC で見ると衝突（蹴り合い）＝**究が通話を見れない/bot を蹴れない**。
- 前進策: `YAY_WATCH_UID`（究本人の別アカuid）で「究が入ってる通話」を発見→EmoCC として join できるよう発見uidを分離。
  → **bot 専用の別アカウントを用意すれば共存可**（要・究判断: 別アカ作成）。
- 掃除: `yay_api.py leave <conference_id>` で EmoCC の幽霊参加を除去できる。

### 停止の注意（再発防止）
- `tmux kill-session` だけだと Playwright 起動の Chromium が**孤児化して publish し続ける**（音が止まらない）。
  確実に止めるには `pkill -f bot_agora.mjs` + `pkill -f "ms-playwright.*chromium"`。stop フローのSIGTERMハンドラ化は要対応。

---

## 2026-06-03 12:40 JST — 通話自動参加・音楽配信をreal-time化（DL方式廃止）

### 通話自動参加（待ち受け）
- bot を「Emo が通話に入る（`get_active_call_post` で拾える）まで polling→見つけたら自動 join」に変更。
  通話が無い間 crash-loop してたのを待ち受けループ化（既定15秒間隔、`YAY_WAIT_MS`）。
- 実走確認: Emo が通話参加→bot が自動 join（RTC/RTM 両方 ok、他参加者の音声 remote published 受信）。
- **制約（既知）**: bot は Emo(11320230) 自身として入るので、ブラウザ/スマホの Emo と**同一アカウント＝衝突**
  （後から入った方が前を蹴る）。観測したいなら別アカウント推奨。yaylib に `join_conference_call` は無く
  `get_conference_call(call_id)` を呼ぶ＝参加スロット(conference_call_user_uuid)割当＝join。

### 音楽配信を real-time 化（yt-dlp 全件DL廃止）
- 旧: `yt-dlp` で全曲DL→`createBufferSourceAudioTrack`。「lofi hip hop」が10時間配信に当たり400MB DL→激遅で却下。
- 新（real-time）:
  - `/play 曲名|URL`: `yt-dlp -g` で直URLを一瞬取得（DLなし）→ ローカルHTTPで pipe 中継（`/stream?u=`、CORS付与、
    ディスク保存なし）→ `<audio>` progressive 再生 → `captureStream()` → `createCustomAudioTrack` で publish。
    起動 ~数秒・全DLしない。検証: headless Chromium で track が readyState=live、currentTime>0 を確認。
  - `/live [入力名]`: `getUserMedia`（BlackHole等のシステム音声）を直接 publish。yt-dlp 完全不要。
  - 共通コア `publishLiveTrack(mediaStreamTrack)`。captureStream を tainted にしないため proxy が CORS 付与。
- 旧DL方式 `resolve`/`ytdlpToFile` は残置（フォールバック、未使用）。

### 残
- real-time `/play` を**生通話で**最終確認（Emo が通話に居る状態で /play→他参加者に聞こえるか）。
- 同一アカウント衝突の解（bot 専用アカウント or 観測は別アカ）を究と決める。

---

## 2026-06-03 11:55 JST — 認証ブロッカー解決（X bot 検知回避）・1コマンド再ログイン化

**唯一の壁だった「有効トークン取得」を解決。** 効いた手順を `relogin.sh` に仕組み化した。

### 効いた肝（X が「ログインを一時的に制限しました」を出す本当の原因）
- **Playwright 同梱 Chromium は automation フラグ（`navigator.webdriver=true`）が立つ**ため、
  X(Twitter) の bot 検知が反応して、人間が手で押しても「ログインを一時的に制限しました」で弾く。
  → 前回 X OAuth が全滅してた主因はコレ（IP/アカウント制限ではなく automation 痕跡）。
- **解** = 素の Google Chrome を `open -na`（LaunchServices 経由＝automation 痕跡なし）で開く。
  X が普通のブラウザとして扱い、人間ログインが一発で通った（「制限」表示が消えた）。
- X ログインは必ず**人間が手で1回**（`続ける` クリック）。NEVER 自動入力（@emocutesounds BAN リスク）。
- ログイン後、CDP(9222) の cookie `_yay_web_access_token` を `grab_token.mjs` で採取。

### 結果
- `.yay_token` 更新: uid=**11320230**（既存 EmoCC）, **expires=2027-06-03（約1年有効）**
- `yay_api.py check` → `{"ok": true, "bgm_count": 9, "uid": 11320230}`
- 再ログインは `./relogin.sh` 1コマンド（①既存トークン有効ならスキップ ②素Chrome起動 ③Yay窓前面化
  ④人間が1クリック ⑤cookie自動採取 ⑥check まで全自動。人間操作は「続ける」1回だけ）。

### 実走で潰した実バグ（agora_client.html、生通話 conference 130648671 で検証）
1. **RTC codec**: `createClient({codec:'opus'})` は INVALID_PARAMS。`codec` は映像用（vp8/vp9/av1/h264/h265のみ）。
   音声onlyでも有効値必須 → `'vp8'` に修正。
2. **RTM token 未渡し**: `rtm.login()` を引数無しで呼んでて `-10005 DYNAMIC_ENABLED_BUT_STATIC_KEY`。
   → `login({ token: rtmToken })` に修正。
3. **Agora アカウント = uuid（最大の罠）**: RTC/RTM とも uid=11320230 では「署名検証失敗/authorized failed」。
   トークンをデコードしたら **crc_uid = `conference_call_user_uuid` の CRC32 に一致**。
   Yay は Agora を**文字列ユーザーアカウント（conference_call_user_uuid）**で運用してた。
   → RTM userId と RTC join uid を両方 `conference_call_user_uuid` に。RTC は `Number()` せず文字列のまま渡す。

### 実走結果
- ✅ **RTM 開通確認**: `CONNECTED LOGIN_SUCCESS` → `RTM joined+subscribed yay-db148ef1-…`（生通話で実証）。
- ⏳ **RTC**: uuid アカウント修正を適用済み。ただし検証中に通話 130648671 が終了（`active`=参加中の通話なし）。
  RTC音声publishの最終確認は**次に生通話が立った時**（EmoCCが入った状態で `./run_agora.sh`）。
- 補足: トークンは `get_conference_call` 側に入る（`get_active_call_post` 側の agora_channel は空）。yay_api.py は両対応済み。

### 次（最終確認だけ）
- EmoCC(11320230) が通話に入った状態で `./run_agora.sh` → RTC が join できるか・音楽が鳴るか実機確認
- 通れば `/play 曲名` で yt-dlp→RTC publish の実DL/配信を確認

---

## 2026-06-03 02:49 JST — 全面API移行（Agora直結）実装、認証で中断

**Session UUID**: F2EF60B0-7ED0-4828-81CF-9C8D318EECA8

### やったこと
- 究の指示で **DOM/BlackHole 廃止 → Agora 直結**（音声=RTC publisher / チャット=RTM）へ全面移行を実装。
- **設計の核を裏取り**: yaylib 2.0.1（Python, `.venv`）の `get_conference_call` が
  `agora_channel`(RTC channel) + `agora_token`(RTCトークン) を返す。`get_agora_rtm_token` で
  RTMトークン。App ID = `79046b8c9be54945b7f10a4d128d5395`。→ Agora に直接 publisher で入れる。
- 実装一式: `yay_api.py`（creds取得）/ `agora_client.html` + `lib/agora.mjs`（RTC/RTM + ローカル音源HTTP）/
  `lib/music_agora.mjs`（yt-dlp解決）/ `bot_agora.mjs`（新orchestrator）/ ログイン補助スクリプト群。
- **検証済**（トークン非依存）: yaylib 署名が api.yay.space に受理・Agora SDK selftest 合格
  （RTC 4.23.0 / RTM 2.2.4 ロード、`window.YayAgora`、配信サーバ）。

### 詰まった所（認証）
有効な Yay トークンが取れず中断。試した経路は全滅:
1. 保存トークン → expired（`ban_until:null`＝BANではない）
2. ウェブセッション cookie → ログアウト済（`_yay_web_access_token` 消失）
3. X OAuth 自動ログイン → **X が「ログイン一時的に制限」**（自動試行が bot 保護を踏んだ。
   これ以上叩くと @emocutesounds が危険なので中止）
4. `login_with_email` で心当たりメール×`kiwamu0320` → 全ハズレ
5. `yagi230430@gmail.com` は未登録、yaylib に新規登録機能なし

### 今日潰した地雷（HANDOFF §5 に詳細）
- harness がツール終了時に Chrome を巻き込み kill → `launch_yay.sh` を `open -na` 化
- CDP の `browser.close()` が実Chrome本体を閉じる → ライブ接続は disconnect のみ
- watcher の CDP 接続リークで Chrome 不安定化 → 単一接続に修正
- launchPersistentContext のページが外部 connectOverCDP から見えない（pages=0）
- ログイン窓は Playwright同梱Chromium に一本化（実Chrome二重起動が macOS で不安定）

### 残タスク（再開ポイント）
- ⛔ Yay トークン取得（案A: `yagi230430@gmail.com` をアプリ登録→yaylibログイン / 案B: X制限解除待ち→手動1クリック）
- ⛔ トークン入手後: `./run_agora.sh` で実走、RTC音楽が通話で鳴るか実機確認
- ⛔ RTM スパイク: 通話チャットのRTMチャンネル名・メッセージ形式を実通話で確定

### コミット
`Emocute/sketches` main → `e1ba574`（24ファイル、Claude著作）
