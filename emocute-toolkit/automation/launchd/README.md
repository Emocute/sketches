# launchd jobs

`bin/emocute automation install` で `~/Library/LaunchAgents/` に symlink + `launchctl bootstrap`。

ジョブ一覧と頻度は AUTOMATION.md 参照。各 plist は `com.emocute.toolkit.<job>.plist` 命名。

## 手動操作

```bash
# 登録
launchctl bootstrap gui/$(id -u) ~/Downloads/Sketches/emocute-toolkit/automation/launchd/com.emocute.toolkit.daily-mem-drift.plist

# 解除
launchctl bootout gui/$(id -u) ~/Downloads/Sketches/emocute-toolkit/automation/launchd/com.emocute.toolkit.daily-mem-drift.plist

# 即時実行（テスト）
launchctl kickstart -k gui/$(id -u)/com.emocute.toolkit.daily-mem-drift

# 状態確認
launchctl print gui/$(id -u)/com.emocute.toolkit.daily-mem-drift
```

## 注意

- plist 内の絶対パスを `/Users/emocute/` 固定で書いている。他環境では templating 必要。
- `StandardOutPath` / `StandardErrorPath` の directory は事前に `mkdir -p automation/logs` 必要。
- failure 連発（3 回連続）したら `bin/emocute automation install` 側で auto-disable する想定。

## 同梱予定の plist（Phase 1 以降）

- `com.emocute.toolkit.daily-mem-drift.plist` ✅
- `com.emocute.toolkit.daily-cookie-expiry.plist`
- `com.emocute.toolkit.daily-vercel-quota.plist`
- `com.emocute.toolkit.daily-r2-cost.plist`
- `com.emocute.toolkit.daily-pain-extract.plist`
- `com.emocute.toolkit.weekly-revenue.plist`
- `com.emocute.toolkit.weekly-downloads-clean.plist`
- `com.emocute.toolkit.weekly-mcp-usage.plist`
- `com.emocute.toolkit.hourly-session-handoff.plist`
