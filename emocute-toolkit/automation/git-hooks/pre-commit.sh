#!/usr/bin/env bash
# emocute-toolkit pre-commit hook
# Downloads/.git-hooks/pre-commit から呼ばれる想定（symlink）。
# 各 PJ の .git-hooks/pre-commit にも同じ仕組みで配置可。
set -euo pipefail

EMOCUTE="$HOME/Downloads/Sketches/emocute-toolkit/bin/emocute"
[ -x "$EMOCUTE" ] || exit 0  # toolkit が無ければ何もしない

# 1. memory/ 変更が含まれていたら整合性検証
if git diff --cached --name-only | grep -qE '^.claude/projects.*memory/'; then
  "$EMOCUTE" mem index-verify || {
    echo "[pre-commit] memory drift detected. fix or use --no-verify (NOT RECOMMENDED)."
    exit 1
  }
fi

# 2. 販売物 ZIP が staged されていたら audit
ZIPS=$(git diff --cached --name-only --diff-filter=AM | grep -E '\.zip$' || true)
if [ -n "$ZIPS" ]; then
  while IFS= read -r zip; do
    "$EMOCUTE" audit zip-3axis "$zip" || {
      echo "[pre-commit] audit failed: $zip"
      exit 2
    }
  done <<< "$ZIPS"
fi

# 3. Idiograph の差分があれば MBTI banned-words
if git diff --cached --name-only | grep -qE '^Idiograph/'; then
  "$EMOCUTE" game mbti-banned-words Idiograph/ || {
    echo "[pre-commit] MBTI banned words found in Idiograph/"
    exit 3
  }
fi

exit 0
