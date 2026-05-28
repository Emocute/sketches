The keywords "MUST", "NEVER", "SHOULD", "MAY" follow RFC 2119.

# emocute-toolkit

Downloads/CLAUDE.md と Sketches/CLAUDE.md を継承。本ファイルは toolkit 固有のルールのみ。

## 着手プロトコル

新しいセッションで toolkit に着手する時の必須手順:

1. MUST `PLAN.md` の「現在フェーズ」セクションを読んで現状把握
2. MUST `registry/_status.yaml` で各ツールの実装状況確認
3. MUST 着手するツール ID を `registry/<category>/<id>.yaml` で開いて仕様確認
4. MUST 実装は `tools/<id>/` 配下に閉じる（横断 util は `tools/_shared/` のみ）
5. MUST 完了したら `registry/_status.yaml` の `status: implemented` に更新

## ツール ID 命名

`<category>-<short_name>` の kebab-case。例:
- `audit-zip-3axis` — 販売物 3 軸監査
- `release-bump-version` — version bump 自動化
- `studio-suno-verify` — Suno injection verify
- `visual-silence-trim` — ffmpeg silencedetect trim

カテゴリ prefix（PLAN.md と一致）:
- `audit-` 監査・コンプライアンス
- `release-` リリースフロー
- `price-` 価格管理
- `studio-` Studio/Suno/音楽
- `visual-` Visual/MV/ffmpeg
- `sale-` 販売チャネル
- `site-` Site/Nuxt/Vercel
- `game-` Numbloom/Idiograph/Kagebu
- `mem-` memory/MEMORY.md
- `ops-` 横断運用
- `comm-` Discord/通信
- `infra-` R2/Supabase/Cloudflare
- `research-` 分析・メタ

## 実装原則

1. MUST 各ツールは **CLI として単独実行可能** + **emocute サブコマンドとしても呼べる** の両方
2. MUST 副作用ある操作は dry-run mode をデフォルトに（`--apply` で実行）
3. MUST stdout は machine-readable JSON or 人間可読 を `--json` flag で切替
4. MUST log は `~/.claude/notifications/log.jsonl` フォーマット互換で `automation/log.jsonl` に追記
5. MUST 失敗時の exit code を区別（0=成功, 1=ツール内エラー, 2=設定エラー, 3=外部依存エラー）
6. NEVER 個別ツール内で `print` 直叩き。MUST `tools/_shared/logger.py` 経由
7. NEVER 外部 API 直叩き。MUST `tools/_shared/clients/` 経由（retry/cache 統一）

## 自動化（launchd / git-hook）

- launchd plist は `automation/launchd/com.emocute.toolkit.<job>.plist`
- git-hook は `automation/git-hooks/<phase>.sh` 配下、`.git-hooks/` から symlink
- 登録/解除は `bin/emocute automation install|uninstall`

## NEVER

- NEVER credentials を tools/ 配下に hardcode（MUST `~/.config/emocute/credentials.yaml` 参照）
- NEVER 285 案を全部一度に PR 化（カテゴリ単位 + 第 1〜5 波）
- NEVER registry/ を Bash 直編集（必ず `bin/emocute tool <id> update <field>=<value>` 経由）
- NEVER tool 内で別 tool を直接 import（MUST CLI 経由か `tools/_shared/` 経由）
- NEVER `_archive/` 配下のレガシースクリプトを toolkit にコピーしない（参照のみ）

## 関連 PJ への侵食ルール

各 PJ の作業フォルダ（Studio/, Sale/ 等）に **書き込む** ツールは:
1. MUST dry-run でまず diff 出力
2. MUST 該当 PJ の CLAUDE.md ルールを違反しない（例: Sale はバージョン bump 必須）
3. MUST 書き込み先 PJ の SESSION_LOG.md に 1 行追記
