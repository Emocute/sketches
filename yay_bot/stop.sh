#!/bin/zsh
# bot を止める（ブラウザ＝通話は残す）。完全停止は --all でブラウザも閉じる。
tmux kill-session -t yay_bot 2>/dev/null
pkill -f "node bot.mjs" 2>/dev/null
echo "bot 停止"
if [ "$1" = "--all" ]; then
  pkill -TERM -f "user-data-dir=$HOME/.claude/playwright-profile-yay" 2>/dev/null
  pkill -TERM -f "user-data-dir=$HOME/.claude/playwright-profile-music" 2>/dev/null
  echo "ブラウザも停止（通話終了）"
fi
