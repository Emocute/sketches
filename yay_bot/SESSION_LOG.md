# yay_bot SESSION_LOG

時系列の作業記録。詳細設計は `CONCEPT.md`、引き継ぎは `_drafts/HANDOFF_*.md`。

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
