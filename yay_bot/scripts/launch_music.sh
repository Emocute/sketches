#!/bin/zsh
# 音楽ブラウザ Chrome を専用プロファイル＋デバッグ口(9223)で起動。
# 既に 9223 が応答してれば何もしない（多重起動防止・通話を落とさない）。
#
# 【重要・2026-06-02 の知見】
#  - 死因は macOS シングルトンではなく「誰も CDP 接続してないブラウザが約10秒でアイドル回収される」。
#    対策＝bot が起動直後に connectMusic で掴み、毎ループ ping（lib/music.mjs ping）して生かす。
#    Chrome を Yay 用と2インスタンス並走させても、両方が握られていれば共存できる。
#  - `--use-fake-ui-for-media-stream` は当環境で Chromium を遅延クラッシュさせたため使わない。
#    setSinkId 用のデバイスラベル露出は ctx.grantPermissions(['microphone'])（connectMusic）で代替。
#  - 起動先は about:blank（YouTube 直行＋自動再生はアイドル時クラッシュ要因）。/play 時に遷移。
if curl -fsS http://127.0.0.1:9223/json/version >/dev/null 2>&1; then
  echo "音楽ブラウザ すでに起動中 (CDP 9223)"
  exit 0
fi
P="$HOME/.claude/playwright-profile-music"
rm -f "$P/Singleton"* 2>/dev/null  # ステイルロックで起動失敗するのを防ぐ
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="$P" --remote-debugging-port=9223 \
  --remote-debugging-address=127.0.0.1 \
  --no-first-run --no-default-browser-check \
  --autoplay-policy=no-user-gesture-required \
  "about:blank" >/dev/null 2>&1 &
disown 2>/dev/null
echo "音楽ブラウザ(Chrome) 起動 pid=$!（CDP 9223）"
for i in $(seq 1 24); do curl -fsS http://127.0.0.1:9223/json/version >/dev/null 2>&1 && { echo "CDP OK"; break; }; sleep 0.5; done
