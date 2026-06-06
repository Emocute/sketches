#!/bin/zsh
# yay_music_bot 起動（純音楽BOT・YouTube）。Agora RTC(音楽)+RTM(コマンド)に直接参加。
# 前提: .yay_token が有効（無効なら relogin.sh → grab_token.mjs で更新）。通話に対象アカウントが居る状態。
# 注意: yay_bot（個人用フル機能bot）と同一アカウントで同時起動すると SAME_UID で蹴り合う。片方だけ動かすこと。
cd "$(dirname "$0")"

echo "▶ トークン疎通確認"
if ! .venv/bin/python yay_api.py check >/tmp/yay_music_check.json 2>&1; then
  echo "✗ トークン無効。 relogin.sh でトークンを更新してください。"
  cat /tmp/yay_music_check.json; exit 1
fi
echo "✓ token ok"

echo "▶ bot 起動（tmux: yay_music_bot）"
tmux kill-session -t yay_music_bot 2>/dev/null
sleep 1
tmux new-session -d -s yay_music_bot "node bot.mjs 2>&1 | tee /tmp/yay_music_bot.log"
sleep 4
echo "── 状態 ──"
tmux has-session -t yay_music_bot 2>/dev/null && echo "bot: tmux yay_music_bot 稼働中" || echo "bot: 起動失敗"
echo "ログ: tail -f /tmp/yay_music_bot.log"
echo "停止: tmux kill-session -t yay_music_bot && pkill -f 'node bot.mjs'"
