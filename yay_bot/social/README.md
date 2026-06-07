# social — Yay フォロワー成長 bot

grok（[/user/10414701](https://yay.space/user/10414701)、何でも答える AI・544 follower）の運用を再現して
Emo Claude（`/user/11320230`）のフォロワーを増やす。**通話 bot（`bot_agora.mjs`）とは完全に別プロセス**で、
API のみで動くので通話 bot を一切落とさず並走できる（`feedback_yay_bot_no_restart` を侵さない）。

## grok の成長モデル（分析結果）

1. **自動フォロバ** — フォローされたら follow を返す → follower 数が積み上がる
2. **メンション応答** — `@grok 質問` に毒混じり AI キャラで答える → 面白いから人が絡む → 露出 → 新規フォロー
3. **能動リプ** — 人の投稿に分析リプを飛ばして絡みに行く
4. **bio がファネル** — 「フォロー＋メンションで質問→答える＋自動フォロバ」を bio に明記

→ この 4 つを `grow.py` が回す。攻め度=**中**（自動フォロバ＋メンション返信＋おすすめ TL への能動リプ/いいね）。

## 構成

| ファイル | 役割 |
|---|---|
| `grow.py` | 本体。activity feed 検知→フォロバ／返信、おすすめ TL→いいね／能動リプ |
| `persona.txt` | grok 型「何でも答える AI」の system prompt（返信生成に渡す） |
| `bio.txt` | プロフィール文面（集客ファネル）。`--set-bio` で適用 |
| `config.json` | 攻め度・レート上限・quiet hours・dry_run の調整 |
| `state.json` | 実行状態（既読 activity / フォロー済 / 返信済 / いいね済 / レート）。git 除外 |

## 使い方

```bash
./run_social.sh check     # トークン生存＋自分のフォロワー数
./run_social.sh once      # 1パスだけ（dry-run 確認 / cron 向き）
./run_social.sh loop      # 常駐ループ
./run_social.sh bio       # bio.txt を反映（要 dry_run=false）
```

## 安全弁

- **`dry_run: true`（既定）の間は書き込みを一切しない**。「何をするか」をログに出すだけ。
  実運用は究 GO 後に `config.json` の `dry_run` を `false` に。
- レート上限（時間あたり follow/reply/like）＋アクション間スロットル（最短間隔＋ゆらぎ）＋quiet hours `[2,7)`。
- 返信生成の `claude -p` は中立 cwd(tmpdir)＋`--strict-mcp-config`（CLAUDE.md を読まない＝思考漏れ防止）。
- 認証は `.yay_token` の既存アクセストークン流用のみ（新規 oauth=新デバイス検知を避ける）。BAN 回避は yay_bot 全体の方針に準拠。

## calibrate（初回）

メンション通知の `type` 名は実物を見ないと確定できない（Emo Claude はまだ被メンション 0）。
`grow.py` は未知の activity type を `[type] '...'` でログに出す。実際に誰かが `@Claude` した後、
そのログに出た type 名を `config.json.mention_reply.reply_types` に足せば返信が回り出す。

## ガード

- 課金 NEVER。
- 究 GO 前に LIVE 発射しない（`dry_run` は GO 後に究 or 究の指示で false）。
