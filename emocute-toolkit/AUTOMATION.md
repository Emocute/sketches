# AUTOMATION

「気づかない間に走る」状態を実現する管理運用自動化レイヤ。

## 3 つのトリガーソース

| トリガー | 用途 | 例 |
|---|---|---|
| **launchd** | 定期実行（macOS ネイティブ） | daily memory drift scan, hourly session handoff |
| **git-hook** | git 操作起点 | pre-commit audit, post-push deploy quota check |
| **Claude Stop hook** | セッション終了時 | SESSION_LOG 追記, dashboard 更新 |

## launchd ジョブ一覧

すべて `automation/launchd/com.emocute.toolkit.<job>.plist`。  
`bin/emocute automation install` で `~/Library/LaunchAgents/` に symlink + `launchctl bootstrap`。

| Label | 頻度 | コマンド | 目的 |
|---|---|---|---|
| `daily-mem-drift` | 毎日 08:00 | `emocute mem index-verify --notify` | memory/MEMORY.md drift 検出 |
| `daily-cookie-expiry` | 毎日 09:00 | `emocute infra cookie-expiry-monitor` | Playwright cookie 30 日前警告 |
| `daily-vercel-quota` | 毎日 10:00 | `emocute site vercel-quota --notify` | Hobby 枠残数監視 |
| `daily-r2-cost` | 毎日 11:00 | `emocute infra r2-cost-estimator` | egress + 月末コスト |
| `daily-pain-extract` | 毎日 23:00 | `emocute research pain-extract` | 当日 jsonl から痛点抽出 |
| `weekly-revenue` | 月曜 08:00 | `emocute sale revenue-aggregate --week` | 4 チャネル売上集計 |
| `weekly-downloads-clean` | 土曜 22:00 | `emocute ops downloads-weekly-clean --propose` | 直下クリーン提案 |
| `weekly-mcp-usage` | 日曜 23:00 | `emocute research llm-usage-pattern --week` | MCP コスト週次 |
| `hourly-session-handoff` | 毎時 :55 | `emocute ops session-handoff-snapshot` | 現在状態を md 化 |

`--notify` 付き失敗時は `terminal-notifier`（既存）で alert + `Glass.aiff -v 0.5`。

## git-hook 一覧

`automation/git-hooks/` を Downloads ルートと各 PJ の `.git-hooks/` に symlink（`core.hooksPath` で既に設定済）。

| Phase | スクリプト | 内容 |
|---|---|---|
| `pre-commit` | `pre-commit.sh` | 1) audit-zip-3axis を変更 ZIP に / 2) mem-index-verify / 3) audit-personal-info-scan |
| `commit-msg` | `commit-msg.sh` | semantic prefix 検証 + 日本語品質（既存 + 強化） |
| `pre-push` | `pre-push.sh` | 1) ops-pre-push-safety / 2) site-vercel-quota（site PJ のみ） |
| `post-push` | `post-push.sh` | 1) automation/log.jsonl に push 記録 / 2) dashboard 更新 |
| `post-merge` | `post-merge.sh` | mem-index-verify + 通知 |

各 hook は最終的に `emocute hook <phase>` を呼ぶ。Bash 側は薄い wrapper。

## Claude Code Stop hook 統合

既存 `~/.claude/hooks/notify_stop.sh` に以下を追記:

```bash
# emocute-toolkit 統合（既存処理の後）
if [ -x "$HOME/Downloads/Sketches/emocute-toolkit/bin/emocute" ]; then
  "$HOME/Downloads/Sketches/emocute-toolkit/bin/emocute" hook stop \
    --pj "$(basename "$PWD")" \
    --uuid "$CLAUDE_SESSION_UUID" \
    --summary "$STOP_SUMMARY" \
    >/dev/null 2>&1 &
fi
```

`emocute hook stop` が:
1. `ops-session-log-append` を該当 PJ で実行
2. `ops-incomplete-task-carry` で未完了 task 検出
3. dashboard data 更新

## SessionStart hook 統合

既存 `~/.claude/hooks/rename_terminal.sh` に追記:

```bash
if [ -x "$HOME/Downloads/Sketches/emocute-toolkit/bin/emocute" ]; then
  "$HOME/Downloads/Sketches/emocute-toolkit/bin/emocute" hook session-start \
    --pj "$(basename "$PWD")" \
    --uuid "$CLAUDE_SESSION_UUID" \
    >/dev/null 2>&1 &
fi
```

役割:
1. 前回セッション handoff を読み出して標準出力に
2. `_status.yaml` の進行中ツールを表示
3. memory drift があれば warning

## dashboard

`dashboard/index.html` を Chrome `--app=` で起動:
- 現在進行中ツール
- 直近 50 実行ログ
- フェーズ別 progress bar（285 中何個 implemented か）
- 失敗中のジョブ一覧
- pain extract 直近 7 日

`launchctl` で常駐ではなく、`emocute dashboard open` で手動起動 or 朝の launchd で 1 回起動。  
既存 `~/.claude/notifications/viewer.html`（サブモニタ左上）の **横** に配置する想定（右側 1920+960, 0）。

## 解除

```bash
emocute automation uninstall
# → 全 LaunchAgent bootout + git-hook unlink + stop hook 追記行削除
```

## 設定セキュリティ

- credentials は `~/.config/emocute/credentials.yaml`（644 ではなく 600）
- launchd plist 内に credentials 直書き禁止
- 全 hook で credentials を `cat` などで stdout に出さない（log にも書かない）

## 失敗時のリカバリ

| 状況 | 対応 |
|---|---|
| launchd ジョブが失敗連発 | terminal-notifier で alert + log.jsonl に error 記録、3 回連続失敗で auto-disable |
| git-hook で commit blocked | エラーメッセージに「`--no-verify` で bypass」案内（NEVER 安易な bypass、原因修正推奨） |
| Stop hook が遅延 | 5 秒タイムアウト + background 実行（Claude セッション体感に影響させない） |

## モニタリング

- `automation/log.jsonl` を `~/.claude/notifications/log.jsonl` にも同行追記して、既存通知ビューアに統合
- weekly で `emocute research llm-usage-pattern` が toolkit 自体のコストも計測

## 命名

| 接頭辞 | 意味 |
|---|---|
| `com.emocute.toolkit.` | toolkit 由来の LaunchAgent label |
| `emocute-` | git-hook script 名 |
| `_toolkit_` | log.jsonl の tool フィールドで内部処理を示す（個別ツールと区別） |
