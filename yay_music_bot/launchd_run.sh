#!/bin/zsh
# launchd(KeepAlive)から呼ばれる起動ラッパ。node bot.mjs を exec で立ち上げ続ける。
# .yay_watch（追尾uid）を唯一の源として毎回読む。token は失効してても bot は待ち受けで idle するので
# launchd 的には生きたまま（失効時の自動 relogin は人手の X ログインが要るので別途 `yaybot relogin`）。
cd "$(dirname "$0")"
[ -f .yay_watch ] && export YAY_WATCH_UID="$(tr -d '[:space:]' < .yay_watch)"
exec /opt/homebrew/bin/node bot.mjs
