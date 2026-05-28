# PLAN

5 フェーズ × 285 ツール候補のロードマップ。  
各フェーズは独立して着手可能（次フェーズ依存最小）。各ツールは `registry/<category>/<id>.yaml` に仕様あり。

## 現在フェーズ

**Phase 1: 即効性 12 ツール** ✅ 完了（2026-05-29）

- 12 tools all implemented + smoke tested
- mem-index-verify が実 drift（259 行・60 件 rule 違反・6 orphans）検出
- game-mbti-banned-words が Idiograph game.html の sale-path hits 検出（要修正）
- price-cross-check が Kagebu/Studio の memory 不整合検出

次は Phase 2（Studio/Suno 30）。

---

## Phase 0: Foundation（土台、1 セッション）

**目標**: モノレポ + CLI + registry + 自動化骨格まで通す。

| ID | タスク | 完了基準 |
|---|---|---|
| F-01 | ディレクトリ骨格 | `bin/ tools/ automation/ registry/ dashboard/ docs/ tests/` 作成済 |
| F-02 | CONCEPT.md / CLAUDE.md / ARCHITECTURE.md | 全部書かれている |
| F-03 | PLAN.md / AUTOMATION.md / README.md | 全部書かれている |
| F-04 | `bin/emocute` スケルトン | `emocute --help` が動く |
| F-05 | `tools/_shared/logger.py` | log.jsonl 追記できる |
| F-06 | `tools/_shared/config.py` | `~/.config/emocute/` 読込できる |
| F-07 | registry/ カテゴリ別 YAML | 13 カテゴリ × 各 N ツールの spec stub |
| F-08 | `registry/_status.yaml` | 全 285 ツールの status: planned |
| F-09 | `tools/_template/` | 新ツール起こす雛形 |
| F-10 | git commit + push | Sketches repo に反映 |

---

## Phase 1: 即効性高 12 ツール（次セッション）

「易」かつ「価値高」かつ外部 API 依存少。これだけで日常運用負荷の 40% は削減見込み。

| 順 | Tool ID | カテゴリ | 概要 |
|---|---|---|---|
| 1 | `audit-zip-3axis` | audit | 販売物 ZIP の薬物/第三者IP/個人情報/身内ラフ表現 grep 監査 |
| 2 | `release-bump-version` | release | ZIP 中身変更検知 → version bump + CHANGELOG prepend + 旧 ZIP 退避 |
| 3 | `price-cross-check` | price | memory/Site/BOOTH/Gumroad の価格 cross check |
| 4 | `mem-auto-split` | mem | MEMORY.md 200 行超で古い topic を `_archive/` に分離 |
| 5 | `mem-index-verify` | mem | memory/*.md と MEMORY.md の整合性検証 |
| 6 | `visual-silence-trim` | visual | ffmpeg silencedetect → trim ワンショット |
| 7 | `visual-scale-pad-even` | visual | 奇数解像度 → 偶数化（MediaRecorder 対策） |
| 8 | `visual-chrome-app-launch` | visual | Chrome `--app=` + aspect 自動 window-size |
| 9 | `site-vercel-quota` | site | Vercel deploy quota 残数監視 + bundle commit 提案 |
| 10 | `site-dl-integrity` | site | Site product.ts × R2 ファイル一覧 突合 |
| 11 | `game-mbti-banned-words` | game | Idiograph の MBTI 商標侵害語スキャン |
| 12 | `ops-session-log-append` | ops | SESSION_LOG.md 自動追記（UUID/start/end） |

**完了基準**: 12 個すべて `--help` + dry-run + apply が動く + integration test 1 本ずつ。

**実装結果（2026-05-29）**: 12/12 完了。tests/ 配下の integration test は Phase 2 と並行。
Real-world findings:
- `mem-index-verify`: MEMORY.md 259 行・60 rule violations・6 orphans 検出
- `game-mbti-banned-words`: Idiograph/game.html に MBTI 4 タイプ名 hardcode 検出
- `price-cross-check`: Kagebu (¥1000/5800/9800) と Studio ($24/$49) の memory inconsistent
- `mem-auto-split`: 1 section （人格マップ 40d old）を split candidate として提案

---

## Phase 2: Studio / Suno / 楽曲制作 30 ツール

第 1 波の delivery pipeline ができてから着手。

| 優先度 | ID | 概要 |
|---|---|---|
| 高 | `studio-suno-verify-loop` | Suno create='ok' 信用せず workspace 確認 |
| 高 | `studio-suno-render-hook` | 生成完了 → suno_render.py → Chrome 自動 |
| 高 | `studio-landr-parallel` | LANDR 複数タブ並列投入（62 曲を 2-3 日に） |
| 高 | `studio-stretch-versions` | render 後 0.9x/1.1x 自動生成 |
| 高 | `studio-banned-artist-scan` | banned_artist_names.txt との grep 検証 |
| 中 | `studio-suno-filter-bypass` | フィルタ reject → 同義語自動置換 |
| 中 | `studio-suno-length-verify` | MP3 1分 / 歌詞 2分尺 検証 |
| 中 | `studio-batch-mcp-wrapper` | studio_auto.py の MCP 化（token 1/50） |
| 中 | `studio-album-zip-builder` | LICENSE/README/ジャケ統合 ZIP |
| 中 | `studio-id3-tag-batch` | ID3 タグ一括更新 |
| 中 | `studio-audio-highlight-30s` | 30 秒ハイライト自動検出 |
| 中 | `studio-loudness-report` | LUFS/LRA/TP 自動レポート |
| 中 | `studio-midi-chord-extract` | MIDI → text chord 抽出 |
| 中 | `studio-midi-voice-leading` | voice leading 検証 |
| 中 | `studio-chord-dict-sync` | HarmonyScope output → SQLite |
| 中 | `studio-bach-chorale-verify` | Bach コラール最小検証 |
| 中 | `studio-sample-pack-builder` | 30s 切出 → ZIP |
| 中 | `studio-audio-fingerprint-dedupe` | 重複検出 |
| 中 | `studio-melody-chord-recommend` | melody → chord 推薦 |
| 中 | `studio-credit-tracker` | Suno credit/refund 管理 |
| 中 | `studio-changelog-from-suno` | Suno prompt/歌詞 → CHANGELOG prepend |
| 低 | `studio-fft-spectrum` | リアルタイム FFT 可視化 |
| 低 | `studio-melody-contour` | melody contour 分析 |
| 低 | `studio-humanize-midi` | velocity/timing randomize |
| 低 | `studio-lyric-meter` | 音節カウント |
| 低 | `studio-arrangement-density` | density visualizer |
| 低 | `studio-suno-style-catalog` | style library 自動 catalog |
| 低 | `studio-groove-half-auto-verify` | 実音源 groove 確認補助 |
| 低 | `studio-suno-prompt-tuner` | parameter auto-tuner |
| 低 | `studio-production-phase-fsm` | phase state machine |

---

## Phase 3: Visual / MV / ffmpeg / 録画 30 ツール

mvtool.py の段階的ラッパー化が中心。

| 優先度 | ID | 概要 |
|---|---|---|
| 高 | `visual-concat-fade` | concat + fade ワンショット |
| 高 | `visual-crf-auto` | 用途別 bitrate 逆算 CRF |
| 高 | `visual-overlay-batch` | watermark/logo 一括 |
| 高 | `visual-obs-remote` | OBS WebSocket START/STOP |
| 高 | `visual-thumbnail-multi-aspect` | サムネ 1:1/16:9/9:16 自動 |
| 高 | `visual-mvtool-autopilot` | MP3 → MV 1 コマンド |
| 高 | `visual-vertical-crop-smart` | 16:9 → 9:16 smart zoom |
| 高 | `visual-ogp-generator` | 曲名+ジャケ → 1200×630 |
| 高 | `visual-ffprobe-verify` | 解像度/FPS/codec/duration 検証 |
| 中 | `visual-webm-mp4-fallback` | コーデック多重試行 |
| 中 | `visual-mediarecorder-seg-concat` | seg 自動結合 |
| 中 | `visual-canvas-png-seq` | Canvas → PNG → MP4 |
| 中 | `visual-three-js-mp4-export` | Three.js → MP4 |
| 中 | `visual-platform-versions` | TikTok/Reels/X Shorts 多版 |
| 中 | `visual-hls-segment` | HLS adaptive 分割 |
| 中 | `visual-lrc-srt-json` | LRC/SRT ↔ JSON + timing UI |
| 中 | `visual-whisper-srt` | STT → SRT |
| 中 | `visual-karaoke-preset` | karaoke 同期 |
| 中 | `visual-mvtool-gui` | Tkinter GUI |
| 中 | `visual-lut-color-grading` | LUT 適用 |
| 中 | `visual-loudness-report` | studio と共有可 |
| 中 | `visual-shader-preset-catalog` | WebGL shader 一覧 |
| 中 | `visual-recording-fps-verify` | フレームレート不一致警告 |
| 低 | `visual-canvas-raster-pipeline` | raster 録画パイプライン |
| 低 | `visual-polyglot-markup` | lang="ja"/"en" 自動 |
| 低 | `visual-flag-svg-generator` | ISO 3166-1 国旗 |
| 低 | `visual-hls-streaming-preview` | R2 連携 preview server |
| 低 | `visual-color-space-verify` | sRGB/DCI-P3 検出 |
| 低 | `visual-stabilization` | 手振れ補正 |
| 低 | `visual-deinterlace-auto` | interlaced 自動検出 |

---

## Phase 4: Sale / Site / Game / Infra 50 ツール

販売・販路・サイト基盤・ゲーム PJ・インフラを 1 フェーズに統合。

### Sale（販売チャネル）
- `sale-channel-sync` マルチチャネル在庫 sync
- `sale-coupon-bulk-mail` クーポン一括発行 + Resend 配信
- `sale-philtz-redirect-manager` 旧 Philtz → 新 Emocute Lab redirect
- `sale-revenue-aggregate` 4 チャネル横断売上集計
- `sale-fee-simulator` チャネル別手数料計算
- `sale-tax-doc-generator` 確定申告ドラフト
- `sale-confirm-mail-dashboard` Stripe → Supabase → Resend 可視化
- `sale-mail-template-bilingual` JA/EN 並列テンプレ管理
- `sale-audience-segmentation` Resend Audiences フィルタ
- `sale-mail-retry-manager` Resend 配信失敗 retry
- `sale-x-post-bilingual` JP+EN 1 ポスト生成
- `sale-utm-shortener` 短縮 + UTM 自動
- `sale-post-replicator` 過去ポスト再投稿ローテ
- `sale-calendar-auto-post` X/Bluesky/Discord 自動告知
- `sale-tunecore-meta-sync` TuneCore メタデータ pull
- `sale-dsp-reach-check` Spotify/Apple/YT Music 到達確認
- `sale-spotify-playlist-pitch` playlist pitch tracker
- `sale-takedown-uri-list` DMCA URI 一覧生成
- `sale-landr-contract-reminder` アルバム完成 → 契約 remind
- `sale-cover-multi-size` ジャケ多サイズ自動
- `sale-en-native-score` EN 翻訳 native 度
- `sale-interview-template` 取材設問テンプレ
- `sale-interview-diff-tracker` 原稿 v1→vN diff
- `sale-press-news-collect` 掲載記事 → news.ts append
- `sale-style-guide-checker` 身内ラフ表現スキャン

### Site
- `site-orphan-pages-purge` 孤立ページ自動パージ
- `site-hreflang-generator` hreflang タグ生成
- `site-schema-org-inject` Product/AudioObject schema
- `site-vercel-analytics-export` 週次 Sheets export
- `site-keyword-rank-monitor` 検索順位監視
- `site-vercel-env-add` preview env 自動追加
- `site-asset-cache-bust` public/ 差替 ?v= 自動
- `site-config-schema-validator` nuxt/.env.example JSON schema
- `site-bundle-analyzer` Vercel deploy 前 bundle size
- `site-sitemap-rebuild` 一括 SEO sitemap 再生成

### Game（Numbloom / Idiograph / Kagebu / HarmonyScope / Sketches）
- `game-numbloom-persona-filter` ペルソナフィルター CLI
- `game-numbloom-poc-validate` game.html 構文・ロジック検証
- `game-numbloom-card-art-score` カードアート品質スコア
- `game-numbloom-banned-words` 世界観禁止語検出
- `game-numbloom-disc-events` ディスク周期イベント生成
- `game-numbloom-voice-consistency` キャラ口調一貫性
- `game-numbloom-hand-layout-lock` 手札レイアウト不可侵検証
- `game-numbloom-idiograph-map` 25 人格 × 16 型 マッピング
- `game-idiograph-name-generator` 16 タイプ独自名生成
- `game-idiograph-theme-generator` 世界観テーマ 3-5 案
- `game-idiograph-axis-builder` Big Five → 4 軸
- `game-kagebu-role-prefix-gen` 25 人格ロールプレ生成
- `game-kagebu-zip-builder` ZIP 自動ビルド
- `game-persona-cross-checker` 3 PJ 人格 cross check
- `game-roleplay-product-page` Gumroad/BOOTH ページ自動
- `game-persona-glossary` 用語集 / locale 辞書
- `game-harmonyscope-cargo-runner` Rust 並列テスト
- `game-harmonyscope-plugin-pkg` VST3/CLAP パッケージ
- `game-chord-dict-sqlite` chord 辞書 SQLite
- `game-ios-theory-lab-poc` iOS POC ビルダー
- `game-sketches-index` Sketches 自動索引

### Infra（R2 / Supabase / Cloudflare / Vercel）
- `infra-r2-waf-fallback` 403 → osascript JS fallback
- `infra-r2-cost-estimator` egress + 月末コスト
- `infra-cf-dns-ssl-monitor` DNS/SSL 異常 alert
- `infra-supabase-webhook-monitor` webhook failure 検出
- `infra-supabase-schema-migrate` DDL apply + rollback
- `infra-stripe-security-audit` PCI compliance scan
- `infra-credentials-vault` credentials 自動抽出 + 安全保存
- `infra-totp-keychain` TOTP Keychain 自動入力
- `infra-cookie-expiry-monitor` Playwright cookie 期限

---

## Phase 5: 横断運用・通信・研究 残全 50 ツール

Phase 0-4 で土台と主要機能が揃ったので、ここは「あれば便利」系をまとめて。

### Ops（横断運用）
- `ops-session-handoff-md` handoff 自動生成
- `ops-pj-start-unified` PJ 起動 CLI 統一
- `ops-memory-backlink-index` Obsidian graph 最適化
- `ops-obsidian-elasticsearch` vault 索引（135K files）
- `ops-obsidian-auto-launch` 起動 hook
- `ops-archive-auto-classify` `_archive/loose_<date>/` 分類
- `ops-file-routing` 新規生成物自動配置
- `ops-downloads-weekly-clean` 直下クリーンアップ
- `ops-cache-safe-rm` 再生成キャッシュ削除
- `ops-commit-msg-lint-strong` semantic + 日本語品質
- `ops-pre-push-safety` quota+merge+tracking 検証
- `ops-failure-mode-early-check` 前回失敗ログ抽出
- `ops-apple-notes-sync` Apple Notes ↔ TODO.md
- `ops-task-monthly-archive` 完了 task archive
- `ops-aiff-context-notify` 状況別 aiff
- `ops-idle-alert` 10 分超 → aiff + ブロック表示
- `ops-priority-notify` 複数 PJ 並行優先度
- `ops-mcp-usage-log` MCP 月次コスト
- `ops-mcp-scanner-extend` disable 提案
- `ops-local-source-cache` URL → ~/Downloads/refs/

### Comm（Discord / メール / SNS）
- `comm-discord-reply-guard` 不利情報 10 カテゴリ事前ガード
- `comm-discord-one-point-deepdive` ABCDE 列挙禁止フォーマッタ
- `comm-discord-arata-snapshot` DM 月次スナップショット
- `comm-discord-group-context-split` グループ DM context 分離
- `comm-resend-failure-dashboard` 既に Sale にあるが Comm 視点で別 view

### Research / Meta
- `research-pain-extract` 「面倒/毎回/弾かれた」自動抽出ダッシュボード
- `research-dev-metrics` git log 統計
- `research-llm-usage-pattern` MCP & LLM API 使用パターン
- `research-incomplete-task-carry` セッション跨ぎ未完了 carry over
- `research-llm-eval-archive` 外部 LLM 評価結果 archive

### Mem（追加）
- `mem-stale-detect` 90 日未参照 detect
- `mem-duplicate-detect` 重複保持検出

### Audit（追加）
- `audit-personal-info-scan` git history 含む個人情報 scan
- `audit-license-cross-check` 年号・連絡先・著者 cross check
- `audit-old-philtz-residue` 旧ブランド残置検出
- `audit-id3-completeness` ID3 完全性

### Sale 追加
- `sale-booth-coupon-workaround` BOOTH Apps 経由
- `sale-stripe-meta-builder` 旧 philtz.com 警告
- `sale-confirm-mail-flow-test` E2E test

### Windows / その他
- `env-windows-vm-setup` Win Smoke テスト VM
- `env-windows-compat-ci` Win 互換性 CI
- `env-vst3-cross-platform-validator` macOS↔Win

### dashboard / 内部
- `internal-dashboard-html` 進捗ダッシュボード
- `internal-tool-template-gen` `emocute tool new <id>` 雛形
- `internal-registry-bulk-import` 285 案 YAML 一括生成
- `internal-changelog-gen` CHANGELOG 自動生成
- `internal-toolkit-version-bump` toolkit 自体の version
- `internal-uninstall-script` 全自動化解除

---

## トラッキング

- 各フェーズ完了時に `registry/_status.yaml` の `phase_completed` を更新
- セッション終了時に PLAN.md 末尾の「直近セッションメモ」に 1 行追記

## 直近セッションメモ

- Phase 0 着手（Foundation）
