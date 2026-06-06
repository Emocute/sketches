# yay_music_bot — ホスト型SaaS 艦隊アーキテクチャ【保留・将来参照】

> ⚠ **2026-06-06 究判断で保留。** Yay ログインは「Xで続ける」= Xアカ紐付けのため、複数アカ化は
> X垢の量産が必要＝Yay/X 両方の規約違反＆BAN祭りの的。捨てメアド量産も不可と判明。
> よって**大規模 SaaS 艦隊はやらない**。当面は **Yay で小規模運用**（究の実垢＋少数の実アカのみ、
> 垢ファーミングなし）。本書はその時のための設計メモとして残す（実装は着手しない）。
> 小規模運用に要る分（アカ別token切替・`fleet.sh`）は実装済で、実アカ2〜3個ならそのまま回せる。

サブスク提供（究が艦隊を回し、客は何もインストールせず Yay 通話に bot を呼べる）の設計。
2026-06-06 起票。emocutelab 既存資産（Supabase/Stripe/Site/Resend/Cloudflare）を管制塔に流用する想定だった。

## 全体像（2層）

```
[管制塔 / Control Plane]  ── emocutelab 資産
  Site(Nuxt) 客ダッシュボード  → Supabase(客/サブスク/セッション/アカウントプール)
                              → Stripe(サブスク課金)  → Resend(通知)
  Dispatcher API（空きbotアカを客の通話へ割当）
        │  割当指示（accountX → 客の通話 callId/uid）
        ▼
[艦隊 / Workers]  ── このPJ（bot.mjs）
  worker1 = botアカ1 + token1  ─┐
  worker2 = botアカ2 + token2  ─┤ 各 worker = 1アカ = 1通話（1アカ=同時1通話の制約）
  worker3 = botアカ3 + token3  ─┘ fleet.sh で並走、watchUid=客uid の通話に入る
```

- **1 worker = 1 Yay アカウント = 同時1通話**。N アカで N 通話を並列に捌く（スケールはアカ数で決まる）。
- worker のアカ別 token 切替は実装済（`yay_api.py` の `YAY_TOKEN_FILE`/`YAY_DEVICE_FILE`、worker は `YAY_SELF_UID`/`YAY_WATCH_UID` を env で受ける）。
- `fleet.sh` が `accounts.json` を読んで「1アカ=1tmux」で起動する土台まで完成。

## ⚠ 最大の未検証リスク（先に潰すべき核心）

**「bot アカが"他人(客)の通話"に入れるか」が未検証。** 現状は bot が自分のアカの通話に入る経路しか実走確認していない。
SaaS は bot アカ ≠ 客。客の通話に入るには:

1. 客の **Yay user id**（または call_id）を知る → `get_active_call_post(客uid)` で通話発見
2. その通話に bot アカが**参加できる権限**があるか（Yay 通話が follow/招待ゲートの場合、bot アカが客をフォロー/招待される必要がありうる）
3. `get_conference_call(call_id)` で参加スロット(conference_call_user_uuid)が割り当たるか（=join 成立）

→ **検証手順（究が安全に試す）**: bot 用の2つ目のYayアカを用意 → 究の別端末で通話を立てる → worker に `YAY_WATCH_UID=別端末アカのuid` で起動 → 入れるか確認。
ここが通らなければホスト型は成立しない。**Phase 0 として最優先で実証する。**

## ⚠ 事業リスク（目を開けて進む）

- **Yay ToS / bot 検知**: 非公式 Agora 直結 + 大量 bot アカ = BAN 検知の的。アカ量産は最大のリスク。
  緩和: アカ作成を分散・人間らしい挙動・1アカの稼働を過密にしない・規約を読む。だが本質的リスクは残る。
- **アカウント供給の律速**: 各 Yay アカに X か電話 signup が要る。emocutelab の web 資産では解決しない別問題。
- **課金は究の明示GO必須**（§ 課金ルール）。Stripe Product/Price 作成・サブスク確定は究本人。

## Supabase スキーマ（案）

```
bot_accounts   (id, name, yay_uid, token_ref, status[idle|assigned|in_call|cooldown|banned], last_seen)
customers      (id, yay_uid, email, created_at, stripe_customer_id)
subscriptions  (id, customer_id, stripe_sub_id, plan, status[active|past_due|canceled], current_period_end)
sessions       (id, customer_id, bot_account_id, call_id, started_at, ended_at, status)
```

## ディスパッチャ 状態遷移（案）

```
客が「bot 呼ぶ」押下（要・有効サブスク）
  → 空き(idle)な bot_account を1つ確保 → assigned
  → worker に「客uid の通話へ入れ」指示（watchUid 設定 or 既存workerへ命令）
  → join 成功 → in_call / セッション記録
  → 客が通話終了 or /bye or サブスク失効 → bot 退出 → cooldown → idle
空きアカ無し → 「満員、後でまた」キュー or 上位プラン誘導
```

## 客オンボーディング導線（ホスト型）

1. Site でサインアップ（既存 Google OAuth/email 認証を流用）
2. 自分の **Yay user id** を登録（プロフィールURL から取得する手順を案内）
3. Stripe でサブスク契約
4. ダッシュボードの「bot を呼ぶ」→ Yay で通話を開始 → 空き bot が入る
5. 通話チャットで `/p 曲名` 等、または「○○かけて」で操作（全員可）

## 段階計画

- **Phase 0（最優先・実証）**: 2アカで「他人の通話に入れるか」を実走検証。`fleet.sh` で2 worker 並走も同時確認。
- **Phase 1（艦隊基盤）**: アカ別 token 管理の整備、relogin の複数アカ対応、worker 監視/自動再起動。
- **Phase 2（管制塔)**: Supabase スキーマ適用、Dispatcher API（割当）、worker への指示経路。
- **Phase 3（客導線）**: Site ダッシュボード（Yay id 登録・bot 呼出・状態表示）。
- **Phase 4（課金）**: Stripe サブスク（究GO）。Resend 通知。
- **Phase 5（運用）**: BAN 監視・アカ補充・利用上限・サポート。

## 現状（このPJで完成済）

- 純音楽 bot（`bot.mjs`、YouTube、コマンド+自然言語、全員操作可）
- アカ別 token 切替（`yay_api.py` env 対応）
- 艦隊ランチャ（`fleet.sh` + `accounts.json`、1アカ=1worker 並走）

→ 次の一手は **Phase 0 の実証**（究が2アカ目を用意できたら）。
