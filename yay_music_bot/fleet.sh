#!/bin/zsh
# yay_music_bot 艦隊ランチャ。accounts.json の各アカウントを「1アカ=1worker=1tmux」で並走起動。
#   各 worker は専用 token/device/uid で yay_api を叩き、watchUid（客のuid）の通話に入る。
#   これが「複数アカで同時に飛ばす」土台。ディスパッチャ（自動割当）は別途（docs/ARCHITECTURE_SAAS.md）。
#
# 使い方:
#   cp accounts.example.json accounts.json   # 編集（各アカの token/device/uid/watchUid）
#   ./fleet.sh start     # enabled:true の全アカを起動
#   ./fleet.sh stop      # 全 worker 停止
#   ./fleet.sh status    # tmux セッション一覧
cd "$(dirname "$0")"
CONF="accounts.json"
[ -f "$CONF" ] || { echo "✗ $CONF が無い。 cp accounts.example.json accounts.json して編集して"; exit 1; }

case "${1:-start}" in
  start)
    # node で accounts.json をパースし、enabled なアカごとに env 付き tmux を立てる
    node -e '
      const fs=require("fs");
      const {accounts=[]}=JSON.parse(fs.readFileSync("accounts.json","utf8"));
      for(const a of accounts){
        if(!a.enabled) continue;
        const env=[
          `YAY_SELF_UID=${a.selfUid||""}`,
          `YAY_TOKEN_FILE=${a.tokenFile||".yay_token"}`,
          `YAY_DEVICE_FILE=${a.deviceFile||".yay_device"}`,
          a.watchUid?`YAY_WATCH_UID=${a.watchUid}`:"",
          a.musicVol!=null?`YAY_MUSIC_VOL=${a.musicVol}`:"",
        ].filter(Boolean).join(" ");
        const sess=`music_${a.name}`;
        const log=`/tmp/yay_music_${a.name}.log`;
        console.log(`${sess}\t${env}\t${log}`);
      }
    ' | while IFS=$'\t' read -r sess env log; do
      echo "▶ 起動 $sess ($env)"
      tmux kill-session -t "$sess" 2>/dev/null
      tmux new-session -d -s "$sess" "env $env node bot.mjs 2>&1 | tee $log"
    done
    sleep 3
    echo "── 状態 ──"; tmux ls 2>/dev/null | grep '^music_' || echo "起動セッション無し"
    ;;
  stop)
    tmux ls 2>/dev/null | grep '^music_' | cut -d: -f1 | while read -r s; do tmux kill-session -t "$s" && echo "停止 $s"; done
    pkill -f "node bot.mjs" 2>/dev/null
    echo "全 worker 停止"
    ;;
  status)
    tmux ls 2>/dev/null | grep '^music_' || echo "稼働 worker 無し"
    ;;
  *) echo "usage: $0 {start|stop|status}"; exit 1 ;;
esac
