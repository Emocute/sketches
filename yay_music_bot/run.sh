#!/bin/zsh
# yay_music_bot 起動（純音楽BOT・YouTube）。Agora RTC(音楽)+RTM(コマンド)に直接参加。
# 前提: .yay_token が有効（無効なら relogin.sh → grab_token.mjs で更新）。通話に対象アカウントが居る状態。
# 注意: yay_bot（個人用フル機能bot）と同一アカウントで同時起動すると SAME_UID で蹴り合う。片方だけ動かすこと。
cd "$(dirname "$0")"

# 追跡対象 uid（この人が居る通話を自動で探して入る）。env 優先、無ければ .yay_watch（git管理外）から読む。
# 未設定なら bot 自身(SELF_UID)の通話を探す従来動作にフォールバック。
if [ -z "$YAY_WATCH_UID" ] && [ -f .yay_watch ]; then export YAY_WATCH_UID="$(tr -d '[:space:]' < .yay_watch)"; fi
[ -n "$YAY_WATCH_UID" ] && echo "▶ 追跡対象 uid=$YAY_WATCH_UID の通話を自動追従"

echo "▶ トークン疎通確認"
if ! .venv/bin/python yay_api.py check >/tmp/yay_music_check.json 2>&1; then
  echo "✗ トークン無効。 relogin.sh でトークンを更新してください。"
  cat /tmp/yay_music_check.json; exit 1
fi
echo "✓ token ok"

echo "▶ bot 起動（tmux: yay_music_bot）"
tmux kill-session -t yay_music_bot 2>/dev/null
sleep 1
# tmux サーバの env は引き継がれない場合があるので、追跡uid等をコマンド文字列に明示注入する。
# 空文字 env を注入すると Python 側の default が効かず int('') で落ちるため、値がある変数だけ前置する。
ENV_PREFIX=""
[ -n "$YAY_WATCH_UID" ] && ENV_PREFIX="${ENV_PREFIX}YAY_WATCH_UID='${YAY_WATCH_UID}' "
[ -n "$YAY_SELF_UID" ]  && ENV_PREFIX="${ENV_PREFIX}YAY_SELF_UID='${YAY_SELF_UID}' "
[ -n "$YAY_MUSIC_VOL" ] && ENV_PREFIX="${ENV_PREFIX}YAY_MUSIC_VOL='${YAY_MUSIC_VOL}' "
[ -n "$YAY_CALL_ID" ]   && ENV_PREFIX="${ENV_PREFIX}YAY_CALL_ID='${YAY_CALL_ID}' "
tmux new-session -d -s yay_music_bot "${ENV_PREFIX}node bot.mjs 2>&1 | tee /tmp/yay_music_bot.log"
sleep 4
echo "── 状態 ──"
tmux has-session -t yay_music_bot 2>/dev/null && echo "bot: tmux yay_music_bot 稼働中" || echo "bot: 起動失敗"
echo "ログ: tail -f /tmp/yay_music_bot.log"
echo "停止: tmux kill-session -t yay_music_bot && pkill -f 'node bot.mjs'"
