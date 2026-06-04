#!/bin/zsh
# VOICEVOX エンジン（headless, :50021）の起動/停止/状態。ずんだもん本声の TTS バックエンド。
# 本体は .voicevox_engine/macos-arm64/run（gitignore 済・約2GB）。
#   start  … 既に生きてれば何もしない。死んでれば起動して /version 応答まで待つ
#   stop   … プロセス停止
#   status … /version を叩く
cd "$(dirname "$0")/.."
ENGINE="$(pwd)/.voicevox_engine/macos-arm64/run"
LOG="/tmp/voicevox_engine.log"
URL="http://127.0.0.1:50021"

alive() { curl -s -m 2 "$URL/version" >/dev/null 2>&1 }

case "${1:-start}" in
  start)
    if alive; then echo "✓ 既に稼働中 $(curl -s -m2 $URL/version)"; exit 0; fi
    [ -x "$ENGINE" ] || { echo "✗ エンジン本体が無い: $ENGINE"; exit 1; }
    echo "▶ VOICEVOX エンジン起動…"
    "$ENGINE" --host 127.0.0.1 --port 50021 >"$LOG" 2>&1 &
    for i in $(seq 1 40); do alive && { echo "✓ 起動完了 $(curl -s -m2 $URL/version)"; exit 0; }; sleep 2; done
    echo "✗ 起動タイムアウト（log: $LOG）"; exit 1 ;;
  stop)
    pkill -f "macos-arm64/run --host 127.0.0.1 --port 50021" && echo "停止した" || echo "稼働してない" ;;
  status)
    alive && echo "✓ 稼働中 $(curl -s -m2 $URL/version)" || echo "✗ 停止" ;;
  *) echo "usage: $0 {start|stop|status}"; exit 1 ;;
esac
