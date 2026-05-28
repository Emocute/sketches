# emocute-toolkit

Emocute モノレポ全 PJ を横串で支える運用・自動化ツール群。  
セッションログ全件（398 jsonl）から抽出した **285 案のツール候補** を統一 CLI として実装する。

## 目的

1. **販売物リリース手順の自動化** — 監査・version bump・CHANGELOG・cross-check を 1 コマンド化
2. **横断的な運用負荷の削減** — SESSION_LOG / memory / Apple Notes / git / Vercel / R2 を統一管理
3. **Studio / Visual / Sale / Site の手作業撲滅** — Suno verify, LANDR 並列, mvtool ラッパー等
4. **管理運用の完全自動化** — git-hook / launchd / Stop hook 連携で「気づかない間に走る」状態

## 最小スコープ（v0.1）

- 統一 CLI `emocute <command>` のエントリポイント
- registry/ に 285 案を YAML 仕様化
- 第 1 波 12 案を実装
- launchd / git-hook で 3 つの定期実行ジョブを稼働

## 技術スタック

| 層 | 技術 | 理由 |
|---|---|---|
| CLI エントリ | Python 3.11+ (typer) | 既存 Studio/Visual と同じ、依存軽量 |
| 個別ツール | Python / Node 混在可 | 既存資産を活かす（mvtool.py, scripts/*.mjs） |
| 設定・registry | YAML | 人間が読める、構造化 |
| dashboard | 単一 HTML + fetch | 既存通知ビューア（`~/.claude/notifications/`）と同居 |
| ストレージ | ローカル JSON / SQLite | 外部依存ゼロ、bootstrap 容易 |
| スケジューラ | launchd（macOS） | 既に通知システムで稼働中 |

## 昇格基準

以下を満たしたら `Downloads/Toolkit/` に昇格 + `Emocute/toolkit` 独立 repo 化:
- 実装ツール 50 以上
- 月間 launchd 実行 100 回以上
- 究以外（人格事業の購入者等）への配布対象になる時

## 非目標

- 販売物そのもの（ツールキットの中身を販売はしない、内部運用ツール）
- 汎用 OSS としての洗練（Emocute 専用の決め打ちで OK）
- 完璧な test coverage（pragmatic、core path のみ）
