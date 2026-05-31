#!/bin/zsh
# yay_bot 一括起動。ブラウザ(冪等)→bot(tmux)。
# 前提: Yay は profile-yay でログイン済み、Emo Claude で通話に参加済み。
#       音楽を流すなら通話参加後に scripts/setup_audio.mjs を1回。
cd "$(dirname "$0")"

echo "▶ ブラウザ起動（冪等）"
zsh scripts/launch_yay.sh
zsh scripts/launch_music.sh

echo "▶ bot 起動（tmux: yay_bot）"
tmux kill-session -t yay_bot 2>/dev/null
sleep 1
tmux new-session -d -s yay_bot "node bot.mjs 2>&1 | tee /tmp/yay_bot.log"
sleep 5

echo "── 状態 ──"
echo "bot: $(ps -eo command | grep 'node bot.mjs' | grep -v grep | grep -v 'zsh -c' | wc -l | tr -d ' ') プロセス"
curl -fsS http://localhost:9222/json/version >/dev/null 2>&1 && echo "Yay Chrome: OK (9222)" || echo "Yay Chrome: NG"
curl -fsS http://localhost:9223/json/version >/dev/null 2>&1 && echo "Vivaldi   : OK (9223)" || echo "Vivaldi   : NG"
echo "ログ: tail -f /tmp/yay_bot.log"
echo "音声: 通話参加後に  node scripts/setup_audio.mjs  （マイク=BlackHole+解除）"
