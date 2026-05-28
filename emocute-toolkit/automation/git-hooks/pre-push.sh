#!/usr/bin/env bash
# emocute-toolkit pre-push hook
set -euo pipefail

EMOCUTE="$HOME/Downloads/Sketches/emocute-toolkit/bin/emocute"
[ -x "$EMOCUTE" ] || exit 0

# Site PJ から push する時は Vercel quota / DL integrity を verify
if [[ "$PWD" == *"/Site"* ]] || git remote get-url origin 2>/dev/null | grep -q emocute-site; then
  "$EMOCUTE" site vercel-quota --notify || true   # warn only, don't block
  "$EMOCUTE" site dl-integrity || {
    echo "[pre-push] DL integrity failed. Fix before pushing to production."
    exit 1
  }
fi

exit 0
