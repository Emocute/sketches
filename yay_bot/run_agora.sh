#!/bin/zsh
# yay_bot 起動（全面API移行版 2026-06-03）。Agora RTC(音楽)+RTM(チャット)に直接参加。
# 前提:
#   - .yay_token が有効（先に login.sh → grab_token.mjs で更新、check が ok）
#   - Emo Claude が対象の通話に参加済み（yay_api.py active が拾える状態）。
#     ※全面API移行では通話参加もAPI化予定だが、現状は通話に居る状態で creds を引く。
cd "$(dirname "$0")"

echo "▶ トークン疎通確認"
if ! .venv/bin/python yay_api.py check >/tmp/yay_check.json 2>&1; then
  echo "✗ トークン無効。 login.sh → grab_token.mjs でトークンを更新してください。"
  cat /tmp/yay_check.json; exit 1
fi
echo "✓ token ok"

echo "▶ VOICEVOX エンジン確認（ずんだもん声の TTS バックエンド）"
zsh scripts/voicevox_engine.sh start 2>&1 | tail -1 || echo "⚠ VOICEVOX 起動失敗（say にフォールバックする）"

echo "▶ bot 起動（tmux: yay_bot、supervise.sh で落ちても自動復帰）"
tmux kill-session -t yay_bot 2>/dev/null
sleep 1
tmux new-session -d -s yay_bot "zsh supervise.sh"
sleep 4
echo "── 状態 ──"
tmux has-session -t yay_bot 2>/dev/null && echo "bot: tmux yay_bot 稼働中" || echo "bot: 起動失敗"
echo "ログ: tail -f /tmp/yay_bot.log"
echo "停止: tmux kill-session -t yay_bot"
