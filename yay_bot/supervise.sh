#!/bin/zsh
# yay_bot 監視ループ（勝手に落ちる対策、2026-06-09）。
# node bot_agora.mjs が何で死んでも自動で立て直す。tmux セッション yay_bot から起動。
#   - 停止は `tmux kill-session -t yay_bot`（このループごと終わる＝意図停止は効く）
#   - トークン失効/瞬断のときは relogin を促しつつ待って再確認（ホットループしない）
#   - 連続クラッシュ時はバックオフ（最大30s）、60s 以上正常稼働できたらバックオフ解除
cd "$(dirname "$0")"
PY=".venv/bin/python"
LOG=/tmp/yay_bot.log

backoff=2
while true; do
  # ① トークン疎通（落ちた原因が失効/DNS瞬断のことがある）。NGなら起動せず待つ
  if ! $PY yay_api.py check 2>/dev/null | grep -q '"ok": true'; then
    echo "[supervise] $(date '+%H:%M:%S') トークン無効/疎通NG → 15s後に再確認（要 ./relogin.sh の場合あり）" | tee -a "$LOG"
    sleep 15
    continue
  fi

  # ② bot 起動（通話は起動時に自動再参加）
  echo "[supervise] $(date '+%H:%M:%S') bot 起動" | tee -a "$LOG"
  start=$(date +%s)
  node bot_agora.mjs 2>&1 | tee -a "$LOG"
  code=${pipestatus[1]}
  ran=$(( $(date +%s) - start ))

  # ③ 60s 以上動けていれば「正常稼働」とみなしバックオフ解除
  if [ "$ran" -ge 60 ]; then backoff=2; fi
  echo "[supervise] $(date '+%H:%M:%S') bot 終了(code=$code, ${ran}s稼働) → ${backoff}s後に再起動" | tee -a "$LOG"
  sleep "$backoff"
  # ④ 短命クラッシュが続くときだけバックオフを伸ばす（最大30s）
  if [ "$ran" -lt 60 ]; then
    backoff=$(( backoff < 30 ? backoff * 2 : 30 ))
  fi
done
