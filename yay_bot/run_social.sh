#!/usr/bin/env bash
# Yay フォロワー成長 bot（通話 bot とは別プロセス）。
# 既定は config.json の dry_run=true ＝書き込みなしで挙動だけログに出す。
set -euo pipefail
cd "$(dirname "$0")"
PY="./.venv/bin/python"
[ -x "$PY" ] || PY="python3"

case "${1:-loop}" in
  check)   exec "$PY" social/grow.py --check ;;
  once)    exec "$PY" social/grow.py --once ;;
  bio)     exec "$PY" social/grow.py --set-bio ;;
  loop|"") exec "$PY" social/grow.py ;;
  *) echo "usage: $0 {check|once|bio|loop}"; exit 2 ;;
esac
