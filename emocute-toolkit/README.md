# emocute-toolkit

Emocute モノレポ（`~/Downloads/`）の日常運用・販売監査・自動化を統合する CLI ツールキット。
セッションログ 398 本から抽出した 285 ツール候補をフェーズ別に実装する。

## 何ができる

`emocute <category> <action>` の単一エントリポイントから:

- 販売物 3 軸監査（薬物/第三者IP/個人情報）
- ZIP version bump + CHANGELOG 自動化
- memory drift 検証 / MEMORY.md 自動分割
- ffmpeg silencedetect → trim、偶数解像度補正、Chrome `--app=` 録画
- Vercel quota 監視、Site DL integrity 突合
- launchd / git-hook による無人運用

## クイックスタート

```bash
# ヘルプ
./bin/emocute --help

# 実装済 + 未実装 一覧
./bin/emocute list --phase 1

# 個別ツール仕様 + dry-run
./bin/emocute audit zip-3axis path/to/album.zip

# 自動化登録（launchd + git-hooks）
./bin/emocute automation install

# ダッシュボード
open dashboard/index.html
```

## ドキュメント

| 文書 | 内容 |
|---|---|
| [CONCEPT.md](CONCEPT.md) | 目的・最小スコープ・昇格基準 |
| [CLAUDE.md](CLAUDE.md) | 着手プロトコル・命名・実装原則 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | ディレクトリ / CLI ルーティング / config / log |
| [PLAN.md](PLAN.md) | 5 フェーズ × 285 ツールのロードマップ |
| [AUTOMATION.md](AUTOMATION.md) | launchd / git-hook / Claude Stop hook 統合 |

## 現在フェーズ

**Phase 0: Foundation** — 土台完成（CLI 骨格 + registry + 仕様 12 本）。
次セッションで Phase 1（即効性高 12 ツール）の実装着手。詳細は PLAN.md。

## 継承

- `~/Downloads/CLAUDE.md`（応答・ブランド・ファイル操作・コミット規約）
- `~/Downloads/Sketches/CLAUDE.md`（サブ PJ 独立性ルール）
- `CLAUDE.md`（toolkit 固有: 着手プロトコル・命名・原則）
