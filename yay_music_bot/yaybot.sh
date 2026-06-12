#!/bin/zsh
# yaybot — Yay 音楽bot の唯一の起動口。ターミナルからも Claude Desktop の Dispatch からも同じ一発で確実に起動する。
#
# Dispatch から: Downloads は dispatchTrustedCodeWorkspaces に入っているので、Dispatch で
#               「yay bot 起動」と言えば agent がこのスクリプトを実行できる →  Sketches/yay_music_bot/yaybot.sh
# ターミナルから: alias `yaybot`（~/.zshrc 登録）か、このファイルを直接実行。
#
# やること（start 時）:
#   1. フル機能bot（yay_bot/bot_agora.mjs）が動いてたら SAME_UID で蹴り合うので警告して中断（--force で強行）
#   2. .yay_token をチェック。失効してたら relogin.sh を自動で呼ぶ（究の X ログイン1クリックだけ手動・自動入力はしない）
#   3. token ok になったら run.sh で tmux 起動（.yay_watch の uid が居る通話を自動追従）
#   4. 状態を1画面で報告
#
# 使い方:
#   yaybot            … 起動（= start）
#   yaybot start      … 起動
#   yaybot stop       … 停止
#   yaybot restart    … 停止して起動し直し
#   yaybot status     … 稼働状況・トークン・追跡uid を表示
#   yaybot start --force … フルbotが動いていても強行起動

cd "$(dirname "$0")"
PY=".venv/bin/python"
SESSION="yay_music_bot"

CMD="${1:-start}"
FORCE=0
[[ "$2" == "--force" || "$1" == "--force" ]] && FORCE=1

_token_ok() { $PY yay_api.py check 2>/dev/null | grep -q '"ok": true'; }

_full_bot_running() { pgrep -f "node bot_agora.mjs" >/dev/null 2>&1; }

_watch_uid() {
  if [ -n "$YAY_WATCH_UID" ]; then echo "$YAY_WATCH_UID";
  elif [ -f .yay_watch ]; then tr -d '[:space:]' < .yay_watch; fi
}

cmd_status() {
  echo "── yaybot status ──"
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "bot      : ● 稼働中（tmux: $SESSION）"
  else
    echo "bot      : ○ 停止"
  fi
  if _token_ok; then echo "token    : ✓ 有効"; else echo "token    : ✗ 失効（要 relogin）"; fi
  echo "追跡uid  : $(_watch_uid)  （この人の通話に自動で入る）"
  _full_bot_running && echo "⚠ 注意   : フル機能bot(bot_agora.mjs)も稼働中。同一アカウントで蹴り合う可能性"
  echo "ログ     : tail -f /tmp/yay_music_bot.log"
}

cmd_stop() {
  tmux kill-session -t "$SESSION" 2>/dev/null
  pkill -f "node bot.mjs" 2>/dev/null
  echo "■ yay_music_bot 停止"
}

ensure_token() {
  if _token_ok; then echo "✓ token ok"; return 0; fi
  echo "✗ トークン失効 → 自動で relogin します。"
  echo "  （素のChromeが開く。究は『ログイン→Xで続ける→続ける』を手で1回だけ。自動入力はしません）"
  RELOGIN_MAX_MIN="${RELOGIN_MAX_MIN:-15}" ./relogin.sh
  if _token_ok; then echo "✓ relogin 完了・token ok"; return 0; fi
  echo "⛔ relogin 失敗。手動で ./relogin.sh を確認してください。"; return 1
}

cmd_start() {
  if _full_bot_running && [ "$FORCE" -ne 1 ]; then
    echo "⛔ フル機能bot(yay_bot/bot_agora.mjs)が稼働中です。"
    echo "   同一Yayアカウントなので、音楽botを起動するとフルbotが通話から蹴られます(SAME_UID)。"
    echo "   フルbotを止めてよければ:  yaybot start --force"
    echo "   （通話中なら yay_bot_no_restart ルール: 究の許可なく落とさない）"
    exit 1
  fi
  ensure_token || exit 1
  ./run.sh
}

case "$CMD" in
  start|"")        cmd_start ;;
  --force)         cmd_start ;;
  stop)            cmd_stop ;;
  restart)         cmd_stop; sleep 1; cmd_start ;;
  status|st)       cmd_status ;;
  *) echo "使い方: yaybot [start|stop|restart|status]  (start に --force でフルbot無視)"; exit 1 ;;
esac
