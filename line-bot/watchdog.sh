#!/bin/zsh
# line-bot 監視塔（launchd で 60 秒毎に起動 → 1 回チェックして終了）。
# KeepAlive で拾えない異常を検知して自動修復する:
#   ① ローカル /health 無応答（プロセスは生きててもイベントループ閉塞）→ server 再起動
#   ② 公開トンネル経由 /health 無応答（ローカルは生きてる）→ tunnel 再起動
#   ③ 90 秒上限を超えて生き残った claude -p（＝詰まり。timeout SIGKILL 不発）→ server 再起動
# claude プロセスは pkill しない（規約）。node 親を launchctl で再起動し、孤児化した子は stdout 閉塞で自然終了する。
set -u
UID_N="$(id -u)"
LOG="$HOME/Library/Logs/linebot/watchdog.log"
SERVER="gui/$UID_N/com.emocute.linebot.server"
TUNNEL="gui/$UID_N/com.emocute.linebot.tunnel"
LOCAL="http://localhost:8787/health"
PUBLIC="https://line-bot.emocutelab.com/health"
STALE_SEC=300   # claude -p がこの秒数を超えて生存＝詰まり（server 側 timeout は 90s）

mkdir -p "$(dirname "$LOG")"
log() { print -r -- "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"; }
restart() { # $1=ラベル $2=理由
  log "RESTART $1 : $2"
  launchctl kickstart -k "$1" >/dev/null 2>&1
}

acted=0

# ① ローカル health
if ! curl -fsS -m 8 "$LOCAL" >/dev/null 2>&1; then
  restart "$SERVER" "local /health 無応答"
  acted=1
fi

# ③ 詰まり: 90s を超えて生き残った claude -p（① で再起動済みなら省略）
if [ "$acted" -eq 0 ]; then
  stale="$(ps -axo etimes=,command= 2>/dev/null | awk -v s=$STALE_SEC '/claude -p/ && $1+0 > s {n++} END{print n+0}')"
  if [ "${stale:-0}" -gt 0 ]; then
    restart "$SERVER" "停滞 claude -p ${stale}本（>${STALE_SEC}s）"
    acted=1
  fi
fi

# ② 公開トンネル（ローカルが生きてる時だけ。server 再起動直後はスキップ）
if [ "$acted" -eq 0 ]; then
  if curl -fsS -m 8 "$LOCAL" >/dev/null 2>&1 && ! curl -fsS -m 12 "$PUBLIC" >/dev/null 2>&1; then
    restart "$TUNNEL" "公開トンネル /health 無応答（ローカルは正常）"
    acted=1
  fi
fi

[ "$acted" -eq 0 ] && exit 0
exit 0
