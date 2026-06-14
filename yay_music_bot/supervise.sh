#!/bin/zsh
# yay_music_bot 自己監視ループ。tmux セッション yaybot の中で回す。
# node bot.mjs が何で落ちても5秒後に立て直す＝常駐。Downloads にアクセスできる通常セッション文脈で動く
# （launchd だと Downloads が TCC 保護で読めず exit 127 になるので、こちらの方式を採用）。
# 追尾uid は .yay_watch を毎ループ読む（途中で変えたら次の再起動で反映）。
cd "$(dirname "$0")"
# CoeFont(ひろゆき声)の API キーがあれば読み込む（.coefont_env は git 管理外、究が中身を入れる）。
[ -f .coefont_env ] && source .coefont_env
while true; do
  [ -f .yay_watch ] && export YAY_WATCH_UID="$(tr -d '[:space:]' < .yay_watch)"
  echo "[supervise $(date '+%m/%d %H:%M:%S')] node bot.mjs 起動 (追尾uid=${YAY_WATCH_UID:-self})"
  node bot.mjs
  code=$?
  echo "[supervise $(date '+%m/%d %H:%M:%S')] bot 終了(code=$code)。5秒後に再起動"
  sleep 5
done
