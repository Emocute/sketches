#!/bin/zsh
# Yay 再ログイン（1コマンド）。2026-06-03 に効いた唯一の手順を仕組み化したもの。
#
# 効いた肝（再発防止メモ）:
#   - Playwright 同梱 Chromium は automation フラグ（navigator.webdriver=true）が立ち、
#     X(Twitter) の bot 検知に「ログインを一時的に制限しました」で弾かれる。
#   - なので素の Google Chrome を `open -na`（LaunchServices 経由＝automation 痕跡なし）で開く。
#     これなら X が普通のブラウザとして扱い、人間ログインが通る。
#   - X ログインは必ず人間が手で1回（自動操作は @emocutesounds BAN リスク。NEVER 自動入力）。
#   - ログイン後、CDP(9222) の cookie `_yay_web_access_token` を grab_token.mjs で採取。
#   - 採れるトークンは約1年有効（uid 11320230 = 既存 EmoCC）。
#
# 使い方:  ./relogin.sh        （窓が前面に出る→「ログイン→Xで続ける→続ける」を手で1回）
#          自動でトークン採取→check まで走り、{"ok":true} で終了。
cd "$(dirname "$0")"
PY=".venv/bin/python"
MAX_MIN="${RELOGIN_MAX_MIN:-15}"

# ① 既存トークンが生きてれば何もしない
if $PY yay_api.py check 2>/dev/null | grep -q '"ok": true'; then
  echo "✓ トークンは既に有効。再ログイン不要。"
  $PY yay_api.py check
  exit 0
fi

# ② 素の Chrome 起動（automation 痕跡なし）
zsh scripts/launch_yay.sh

# ③ Yay 窓を前面化（別インスタンス対策で activate + unminiaturize）
osascript >/dev/null 2>&1 <<'OSA'
tell application "Google Chrome"
  activate
  repeat with w in windows
    try
      if (URL of active tab of w) contains "yay" then
        set index of w to 1
        set miniaturized of w to false
      end if
    end try
  end repeat
end tell
OSA

echo "→ 開いた Chrome で『ログイン → Xで続ける → 続ける』を手で1回押してください。"
echo "  （automation 痕跡なしの素 Chrome なので X 制限に当たりません。自動入力はしません）"
echo "  ログイン検知を最大 ${MAX_MIN} 分ポーリングします…"

# ④⑤⑥ ログイン検知→トークン採取→check をポーリング
deadline=$(( $(date +%s) + MAX_MIN * 60 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  node scripts/grab_token.mjs >/dev/null 2>&1
  if $PY yay_api.py check 2>/dev/null | grep -q '"ok": true'; then
    echo "✓ ログイン成功・トークン採取完了。"
    $PY yay_api.py check
    exit 0
  fi
  sleep 8
done

echo "⛔ タイムアウト（${MAX_MIN}分）。ログインされなかったか cookie 未確立。"
echo "   窓でログイン状態を確認して、もう一度 ./relogin.sh を実行してください。"
exit 1
