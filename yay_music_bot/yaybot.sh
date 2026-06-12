#!/bin/zsh
# yaybot — Yay 音楽bot の制御口（常駐・自動追尾）。
#
# 方式（究指示 2026-06-12「常駐・自動追尾」）:
#   tmux セッション `yaybot` の中で supervise.sh を回し、node bot.mjs を落ちても立て直し続ける＝常駐。
#   Mac ログイン中ずっと待ち受け → 究(.yay_watch のuid)が通話に入ったら自動 join・蹴られても再join。
#   ※ launchd は Downloads が TCC 保護で読めず使えない（exit 127）。tmux supervise はユーザー文脈で動くので可。
#   ※ tmux サーバはターミナルを閉じても生き続けるが、再起動(reboot)では消える → 再起動後は `yaybot` を一回。
#      reboot 後も自動で上げたいなら `yaybot boot-enable`（/bin/zsh に Full Disk Access の一回付与が要る）。
#
# Claude Desktop の Dispatch はプロセスを自分で起動できない（クリップボード手渡しが限界）ので、
# 「言えば入る」は Dispatch ではなくこの常駐で実現する＝そもそも起動操作が要らなくなる。
#
# 使い方:
#   yaybot install    … 常駐化（tmux supervise を起動。最初の一回／reboot後）
#   yaybot            … 今すぐ再起動（= restart。部屋を移った時など即入り直し）
#   yaybot status     … 稼働状況・トークン・追跡uid を表示
#   yaybot stop       … 常駐停止
#   yaybot relogin    … トークン失効時。素Chromeでログイン1クリック→自動で再起動
#   yaybot boot-enable… reboot 後も自動起動（launchd＋Full Disk Access、要一回手動付与）

cd "$(dirname "$0")"
PY=".venv/bin/python"
SESSION="yaybot"
LOG="/tmp/yay_music_bot.log"

CMD="${1:-restart}"

_token_ok()        { $PY yay_api.py check 2>/dev/null | grep -q '"ok": true'; }
_full_bot_running(){ pgrep -f "node bot_agora.mjs" >/dev/null 2>&1; }
_bot_running()     { pgrep -f "node bot.mjs" >/dev/null 2>&1; }
_alive()           { tmux has-session -t "$SESSION" 2>/dev/null; }
_watch_uid()       { [ -f .yay_watch ] && tr -d '[:space:]' < .yay_watch; }

_kill_full_bot() {
  if _full_bot_running; then
    echo "▶ フル機能bot(yay_bot)稼働中 → SAME_UID競合回避のため停止（先にtmux殺してからpkill）"
    tmux kill-session -t yay_bot 2>/dev/null; sleep 1
    pkill -f "node bot_agora.mjs" 2>/dev/null; sleep 1
  fi
}

_kill_self() {
  tmux kill-session -t "$SESSION" 2>/dev/null
  tmux kill-session -t yay_music_bot 2>/dev/null   # 旧方式セッションも畳む
  pkill -f "node bot.mjs" 2>/dev/null
}

cmd_install() {
  _kill_full_bot
  _kill_self
  sleep 1
  tmux new-session -d -s "$SESSION" "zsh supervise.sh 2>&1 | tee $LOG"
  echo "✓ 常駐化（tmux: $SESSION）。Mac ログイン中ずっと待ち受け→自動追尾。"
  sleep 3; cmd_status
}

cmd_restart() {
  if ! _alive; then echo "未常駐 → install します"; cmd_install; return; fi
  _kill_full_bot
  # supervise が走ってるので bot プロセスだけ落とせば5秒で入り直す（現在の通話に再join）
  pkill -f "node bot.mjs" 2>/dev/null
  echo "▶ 再起動（5秒以内に現在の通話へ入り直します）"
  sleep 6; cmd_status
}

cmd_stop() {
  _kill_self
  echo "■ 常駐停止（tmux: $SESSION）。再開: yaybot install"
}

cmd_relogin() {
  RELOGIN_MAX_MIN="${RELOGIN_MAX_MIN:-15}" ./relogin.sh || { echo "⛔ relogin 失敗"; return 1; }
  if _alive; then pkill -f "node bot.mjs" 2>/dev/null; echo "▶ token更新→再起動"; else cmd_install; fi
  sleep 6; cmd_status
}

cmd_boot_enable() {
  # reboot 後の自動起動を launchd で。Downloads が TCC 保護なので /bin/zsh に Full Disk Access が要る。
  local dst="$HOME/Library/LaunchAgents/com.emocute.yaybot.plist"
  mkdir -p "$HOME/Library/LaunchAgents"
  cp -f "$(pwd)/com.emocute.yaybot.plist" "$dst"
  echo "── reboot 後の自動起動セットアップ ──"
  echo "1) システム設定 → プライバシーとセキュリティ → フルディスクアクセス を開く"
  echo "2) ＋ を押し、⌘⇧G で /bin/zsh を入力して追加・トグルON"
  echo "3) 追加できたら:  launchctl bootstrap gui/$(id -u) \"$dst\""
  echo "   （これで reboot 後も自動で上がる。FDAを付けずに bootstrap しても exit 127 で失敗する）"
  echo "plist 設置済: $dst"
}

cmd_status() {
  echo "── yaybot status ──"
  if _alive; then echo "常駐     : ✓ tmux $SESSION 稼働中（落ちても自動復帰）"; else echo "常駐     : ○ 停止（yaybot install で常駐化）"; fi
  if _bot_running; then echo "bot      : ● node bot.mjs 稼働中"; else echo "bot      : ○ プロセス無し（起動中か待機）"; fi
  if _token_ok; then echo "token    : ✓ 有効"; else echo "token    : ✗ 失効 → yaybot relogin"; fi
  echo "追跡uid  : $(_watch_uid)  （この人が通話に入ったら自動join・追尾）"
  _full_bot_running && echo "⚠ 注意   : フル機能bot(bot_agora.mjs)も稼働中。同一アカウントで競合の可能性"
  echo "ログ     : tail -f $LOG"
}

case "$CMD" in
  install)        cmd_install ;;
  start)          _alive && cmd_restart || cmd_install ;;
  restart|"")     cmd_restart ;;
  stop)           cmd_stop ;;
  relogin)        cmd_relogin ;;
  boot-enable)    cmd_boot_enable ;;
  status|st)      cmd_status ;;
  *) echo "使い方: yaybot [install|start|restart|stop|status|relogin|boot-enable]"; exit 1 ;;
esac
