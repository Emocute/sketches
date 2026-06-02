#!/bin/zsh
# Yay 用 Chrome を専用プロファイル＋デバッグ口(9222)で起動。
# 既に 9222 が応答してれば何もしない（多重起動防止）。
# ※ログインと通話参加は手動（cookie は profile に永続）。
if curl -fsS http://127.0.0.1:9222/json/version >/dev/null 2>&1; then
  echo "Yay Chrome すでに起動中 (CDP 9222)"
  exit 0
fi
P="$HOME/.claude/playwright-profile-yay"
# ★open -na で起動（LaunchServices 経由＝呼び出し元シェルの子にならない）。
#   nohup & だと harness がツール終了時にプロセスグループごと掃除して Chrome を巻き込み殺す事故あり（2026-06-03）。
open -na "Google Chrome" --args \
  --user-data-dir="$P" --remote-debugging-port=9222 \
  --remote-debugging-address=127.0.0.1 \
  --no-first-run --no-default-browser-check \
  "https://yay.space/"
echo "Yay Chrome 起動（CDP 9222, open -na）"
for i in $(seq 1 24); do curl -fsS http://127.0.0.1:9222/json/version >/dev/null 2>&1 && { echo "CDP OK"; break; }; sleep 0.5; done
