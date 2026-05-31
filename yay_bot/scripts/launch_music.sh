#!/bin/zsh
# 音楽ブラウザ Vivaldi を専用プロファイル＋デバッグ口(9223)で起動。
# 既に 9223 が応答してれば何もしない（多重起動防止・通話を落とさない）。
# --use-fake-ui-for-media-stream: getUserMedia 自動許可（setSinkId 用にデバイスラベル露出）
# --autoplay-policy: 自動再生許可
if curl -fsS http://localhost:9223/json/version >/dev/null 2>&1; then
  echo "Vivaldi すでに起動中 (CDP 9223)"
  exit 0
fi
P="$HOME/.claude/playwright-profile-music"
"/Applications/Vivaldi.app/Contents/MacOS/Vivaldi" \
  --user-data-dir="$P" --remote-debugging-port=9223 \
  --no-first-run --no-default-browser-check \
  --autoplay-policy=no-user-gesture-required \
  --use-fake-ui-for-media-stream \
  "https://open.spotify.com/" >/dev/null 2>&1 &
echo "Vivaldi(music) 起動 pid=$!（CDP 9223）"
for i in $(seq 1 24); do curl -fsS http://localhost:9223/json/version >/dev/null 2>&1 && { echo "CDP OK"; break; }; sleep 0.5; done
