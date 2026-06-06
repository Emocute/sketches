#!/bin/zsh
# 手動小規模提供: 指定した「友達の Yay user id」の通話に bot を1個入れる（Model A）。
#   友達が通話に入っている状態で実行 → bot がその通話を発見して参加 → 友達が /p 曲名 等で操作。
#
# 使い方:
#   ./serve.sh <友達のYay_user_id> [tokenFile] [selfUid] [musicVol]
#   例) ./serve.sh 12345678                 # 既定アカ(.yay_token)で友達12345678の通話へ
#       ./serve.sh 12345678 .yay_token_bot2 22222222 12   # 別アカ・音量12で
#   停止: ./serve.sh stop <友達のYay_user_id>   または  tmux kill-session -t music_serve_<uid>
#
# 注意:
#   - bot が友達の通話に入れるかは Yay の権限次第（follow/招待ゲートの可能性）。要事前検証（docs/OPERATE_SMALL.md）。
#   - 同一アカで yay_bot(個人)や他の serve と同時起動すると SAME_UID で蹴り合う。アカは1用途に1つ。
cd "$(dirname "$0")"

if [ "$1" = "stop" ]; then
  uid="$2"; [ -z "$uid" ] && { echo "usage: ./serve.sh stop <友達のYay_user_id>"; exit 1; }
  tmux kill-session -t "music_serve_${uid}" 2>/dev/null && echo "停止: music_serve_${uid}" || echo "そのセッションは無い"
  exit 0
fi

WATCH="$1"; TOKEN="${2:-.yay_token}"; SELF="${3:-11320230}"; VOL="${4:-15}"
[ -z "$WATCH" ] && { echo "usage: ./serve.sh <友達のYay_user_id> [tokenFile] [selfUid] [musicVol]"; exit 1; }

echo "▶ トークン疎通確認（token=$TOKEN, selfUid=$SELF）"
if ! YAY_TOKEN_FILE="$TOKEN" YAY_SELF_UID="$SELF" .venv/bin/python yay_api.py check >/tmp/yay_serve_check.json 2>&1; then
  echo "✗ トークン無効。 relogin で $TOKEN を更新して。"; cat /tmp/yay_serve_check.json; exit 1
fi
echo "✓ token ok"

SESS="music_serve_${WATCH}"
LOG="/tmp/yay_music_serve_${WATCH}.log"
echo "▶ bot 起動（tmux: $SESS / 対象通話=友達uid $WATCH）"
tmux kill-session -t "$SESS" 2>/dev/null; sleep 1
tmux new-session -d -s "$SESS" "env YAY_WATCH_UID=$WATCH YAY_TOKEN_FILE=$TOKEN YAY_SELF_UID=$SELF YAY_MUSIC_VOL=$VOL node bot.mjs 2>&1 | tee $LOG"
sleep 4
tmux has-session -t "$SESS" 2>/dev/null && echo "稼働中: $SESS" || echo "起動失敗"
echo "ログ: tail -f $LOG"
echo "停止: ./serve.sh stop $WATCH"
