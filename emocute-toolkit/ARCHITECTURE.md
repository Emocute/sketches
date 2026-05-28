# Architecture

## ディレクトリ構造

```
emocute-toolkit/
├── CONCEPT.md              # 起票・目的・スコープ
├── CLAUDE.md               # 着手プロトコル・実装原則
├── ARCHITECTURE.md         # 本ファイル
├── PLAN.md                 # 5 フェーズ × 285 案ロードマップ
├── AUTOMATION.md           # 管理運用自動化レイヤ仕様
├── README.md               # エントリポイント
│
├── bin/
│   └── emocute             # 統一 CLI（typer）。`emocute <category> <action>` ルータ
│
├── tools/
│   ├── _shared/            # 横断 util
│   │   ├── logger.py       # ~/.claude/notifications/log.jsonl 互換
│   │   ├── config.py       # ~/.config/emocute/ 読込
│   │   ├── clients/        # 外部 API ラッパー（retry/cache）
│   │   │   ├── r2.py
│   │   │   ├── supabase.py
│   │   │   ├── vercel.py
│   │   │   ├── cloudflare.py
│   │   │   ├── booth.py
│   │   │   ├── gumroad.py
│   │   │   └── suno.py
│   │   ├── git_helpers.py
│   │   ├── ffmpeg_helpers.py
│   │   └── dry_run.py
│   ├── audit-zip-3axis/    # ツール 1 個 = 1 フォルダ
│   │   ├── main.py
│   │   ├── README.md
│   │   ├── test_main.py
│   │   └── fixtures/
│   ├── release-bump-version/
│   ├── price-cross-check/
│   ├── ...
│
├── automation/
│   ├── launchd/            # plist テンプレート
│   ├── git-hooks/          # pre-commit, commit-msg, post-push 等
│   ├── stop-hook-hooks/    # ~/.claude/hooks/notify_stop.sh から呼ぶ追加処理
│   └── log.jsonl           # 全 toolkit 実行ログ（追記専用）
│
├── registry/
│   ├── _status.yaml        # 全 285 案の status 一覧（軽量）
│   ├── audit/              # カテゴリ別フォルダ
│   │   ├── audit-zip-3axis.yaml
│   │   └── ...
│   ├── release/
│   ├── studio/
│   ├── visual/
│   ├── sale/
│   ├── site/
│   ├── game/
│   ├── mem/
│   ├── ops/
│   ├── comm/
│   ├── infra/
│   └── research/
│
├── dashboard/
│   ├── index.html          # 進捗ダッシュボード（Chrome --app=）
│   └── data.json           # 自動生成（_status.yaml + log.jsonl から）
│
├── docs/
│   ├── tools-by-category.md
│   ├── changelog.md
│   └── adr/                # Architecture Decision Records
│
└── tests/
    └── integration/        # ツール横断 E2E
```

## CLI ルーティング

```
emocute                          # 全コマンド一覧
emocute <category>               # カテゴリ内ツール一覧
emocute <category> <action>      # 個別ツール実行

# 例
emocute audit zip-3axis ~/Downloads/Sale/_archive/v8.2.zip
emocute release bump-version --pj Sale --target patch
emocute price cross-check --json
emocute studio suno-verify --track-name "..."
emocute visual silence-trim ~/Downloads/2026-05-19.mp4
emocute mem split                # MEMORY.md auto-split
emocute mem index-verify
emocute ops session-log append --pj Studio --uuid ...
emocute infra vercel-quota
emocute automation install       # launchd / git-hook 登録
emocute tool <id> status         # 個別ツールの status 確認
emocute tool <id> update status=implemented
emocute dashboard open           # Chrome --app= で dashboard 起動
```

## データフロー

```
[Claude Code セッション]
     │
     ├──> tools/<id>/main.py 実行
     │         │
     │         ├──> tools/_shared/logger.py
     │         │      └─> automation/log.jsonl 追記
     │         │      └─> ~/.claude/notifications/log.jsonl にも追記（dashboard 統合）
     │         │
     │         └──> tools/_shared/clients/* で外部 API 呼出
     │
     ├──> registry/_status.yaml 更新
     │
     └──> dashboard/data.json 再生成（hook）

[launchd ジョブ]
     │
     └──> bin/emocute <category> <action> --apply
              └──> log.jsonl 追記
              └──> 失敗時は terminal-notifier ポップアップ

[git-hook]
     │
     └──> automation/git-hooks/pre-commit.sh
              ├──> emocute audit pre-commit（薬物名・個人情報 scan）
              ├──> emocute mem index-verify
              └──> 失敗で commit abort
```

## 設定ファイル配置

```
~/.config/emocute/
├── config.yaml             # 全体設定（log level, dashboard port 等）
├── credentials.yaml        # API key（.gitignore 必須）
└── pj_map.yaml             # PJ 名 → Downloads 配下パスのマッピング
```

`credentials.yaml` の参照キー:
- `r2.access_key_id`, `r2.secret_access_key`, `r2.account_id`
- `supabase.url`, `supabase.service_role_key`
- `vercel.token`, `vercel.project_id`
- `cloudflare.api_token`
- `booth.session_cookie`（scrape 用）
- `gumroad.access_token`
- `resend.api_key`
- `suno.bearer`

既存 `Site/docs/auth/.credentials_2026-05-20.md` の値を参照する形が暫定。
完全移行は infra-credentials-vault ツール（registry/infra/）で行う。

## 依存ポリシー

- Python 標準ライブラリ + typer + pyyaml + httpx + rich を基本
- ツール固有依存は `tools/<id>/requirements.txt` に閉じる
- グローバル `requirements.txt` は最小限
- `uv` で管理（macOS で既存環境ある前提）

## ログフォーマット

```jsonl
{"ts":"2026-05-29T05:30:00+09:00","tool":"audit-zip-3axis","pj":"Sale","level":"info","msg":"audit started","meta":{"zip":"..."}}
{"ts":"...","tool":"...","pj":"...","level":"warn","msg":"banned word found","meta":{"word":"...","file":"..."}}
{"ts":"...","tool":"...","pj":"...","level":"error","msg":"...","meta":{...}}
{"ts":"...","tool":"...","pj":"...","level":"done","msg":"audit completed","meta":{"warnings":3,"errors":0,"duration_ms":1234}}
```

dashboard はこれを 2 秒ポーリングして表示。

## バージョニング

- toolkit 自体は `package.json` ライクに `toolkit_version.yaml` で管理
- 個別ツールは `tools/<id>/main.py` 冒頭の `__version__` で
- 大きな変更時に `docs/changelog.md` に prepend
