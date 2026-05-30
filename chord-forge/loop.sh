#!/usr/bin/env bash
# chord-forge / composer 無限ループ — 転調進行を延々鍛造して Pianoteq でレンダ。
#   生成 → MIDI → Pianoteq WAV → gen.html 更新 → sleep → 繰り返し
#
# 使い方:
#   ./loop.sh                 # 既定: 上限 250 本・各本後 6 秒待機
#   MAX=500 SLEEP=15 ./loop.sh
#
# 上限到達で停止する(WAV は 1 本 ~8MB / 48s。延々回すと GB 級になるので無音の暴走防止)。
# 上限を上げたい時は MAX を増やすか、聴き終えた gen/wav/*.wav を間引いてから再起動。

set -u
cd "$(dirname "$0")"

MAX="${MAX:-250}"
SLEEP="${SLEEP:-6}"
PRESET="${PRESET:-NY Steinway D Jazz}"
LOG="gen/loop.log"
mkdir -p gen

ts() { date "+%Y-%m-%d %H:%M:%S"; }
count_wav() { ls gen/wav/*.wav 2>/dev/null | wc -l | tr -d ' '; }

echo "[$(ts)] loop 開始  MAX=$MAX SLEEP=${SLEEP}s preset=[ $PRESET ]" | tee -a "$LOG"

while :; do
  have=$(count_wav)
  if [ "$have" -ge "$MAX" ]; then
    echo "[$(ts)] 上限到達: ${have}/${MAX} 本。停止。" \
         "（上限を上げる: MAX=N ./loop.sh / 間引く: gen/wav を整理して再起動）" | tee -a "$LOG"
    break
  fi
  python3 composer.py one --render --preset "$PRESET" >> "$LOG" 2>&1
  now=$(count_wav)
  size=$(du -sh gen/wav 2>/dev/null | cut -f1)
  echo "[$(ts)] ${now}/${MAX} 本  (gen/wav=$size)" | tee -a "$LOG" >/dev/null
  sleep "$SLEEP"
done

echo "[$(ts)] loop 終了。総数 $(count_wav) 本。gen.html で試聴可。" | tee -a "$LOG"
