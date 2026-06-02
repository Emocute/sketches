#!/bin/zsh
# Yay 再ログイン補助（全面API移行版）。
# トークンは「既存ウェブセッション流用」方針＝oauthせず、ブラウザでログインした cookie を吸う。
#   1) このスクリプトで profile-yay の Chrome(9222) を表示起動
#   2) 開いた窓で Emo Claude として Yay にログイン
#   3) ログインできたら:  node scripts/grab_token.mjs   （.yay_token を更新）
#   4) 確認:  .venv/bin/python yay_api.py check
cd "$(dirname "$0")"
zsh scripts/launch_yay.sh
echo
echo "→ 開いた Chrome で Emo Claude として Yay にログインしてください。"
echo "  終わったら:  node scripts/grab_token.mjs  でトークンを吸い、"
echo "             .venv/bin/python yay_api.py check  で疎通確認。"
