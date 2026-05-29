# line-bot — セットアップ手順

LINE グループに参加する Claude ボット。詳細設計は `CONCEPT.md` 参照。

## 全体像

```
LINEグループ → LINE Messaging API → webhook
                                       │
                          Cloudflare Tunnel（固定URL）
                                       │
                          このMac上の server.mjs (:8787)
                                       │
                          claude -p（Max枠で応答、課金なし）
```

---

## 手順1: LINE Messaging API チャネルを作る（究の手作業・無料）

1. https://developers.line.biz/console/ に LINE アカウントでログイン
2. **新規プロバイダー**を作成（名前は何でも可、例: `Emocute`）
3. そのプロバイダーで **「Messaging API」チャネル**を作成
   - チャネル名 = グループに表示されるボット名（例: `クロ`）
   - 業種など必須項目を適当に埋める
4. 作成後、以下2つの値を控える:
   - **チャネルシークレット**: 「チャネル基本設定」タブ → `Channel secret`
   - **チャネルアクセストークン**: 「Messaging API設定」タブ → `チャネルアクセストークン（長期）` を**発行**
5. 「Messaging API設定」タブで:
   - **応答メッセージ: オフ**（LINE 公式の自動返信を切る）
   - **あいさつメッセージ: オフ**（任意）
   - **Webhook: オン**
6. グループ参加を許可: **「LINE公式アカウント機能」→「グループ・複数人トークへの参加を許可する」をオン**
   （`https://manager.line.biz/` の設定 → 応答設定 にある場合もある）

→ 控えた2値を Claude に渡せば `.env` に書き込む（PWはチャットに貼らず、Claude が直接ファイルへ）。

## 手順2: .env を用意

```bash
cp .env.example .env
# LINE_CHANNEL_SECRET と LINE_CHANNEL_ACCESS_TOKEN を記入
```

## 手順3: サーバ起動

```bash
cd ~/Downloads/Sketches/line-bot
node --env-file=.env server.mjs
```
`[line-bot] :8787 ...` と `[bot] <名前> (<userId>)` が出れば OK。

## 手順4: Cloudflare Tunnel で公開

### お手軽（URLが毎回変わる・検証向き）
```bash
cloudflared tunnel --url http://localhost:8787
```
表示される `https://xxxx.trycloudflare.com` を控える。

### 固定URL（emocutelab.com サブドメイン・本番向き）
```bash
cloudflared tunnel login                       # ブラウザで CF 認可（初回のみ）
cloudflared tunnel create line-bot             # トンネル作成
cloudflared tunnel route dns line-bot line-bot.emocutelab.com
# ~/.cloudflared/config.yml に ingress を設定して:
cloudflared tunnel run line-bot
```

## 手順5: LINE に Webhook URL を登録

LINE Developers → 「Messaging API設定」→ **Webhook URL** に
`https://<上で得たホスト>/webhook` を設定 → **検証**ボタンで Success を確認。

## 手順6: グループに招待してテスト

1. 友人と究のグループに、作ったLINE公式アカウント（ボット）を**友だち追加→グループに招待**
2. グループで「クロ、おはよう」のように接頭辞付きで話しかける → 返事が来れば成功

---

## 運用メモ

- **反応条件**: 既定は `mention_or_prefix`（`クロ`/`くろ`/`bot` を含む発言、または @メンション、またはDMにだけ反応）。全発言に反応させるなら `.env` の `TRIGGER_MODE=always`（Max枠を食うので注意）
- **常時稼働**: Mac 起動中のみ動く。閉じると停止。自動起動したくなったら launchd 化（別途）
- **会話文脈**: `history.json` に直近 `MAX_HISTORY` 件を保存。消せばリセット
- **モデル**: 既定 `sonnet`（速さ・枠効率重視）。`CLAUDE_MODEL=opus` で賢くなるが枠を多く食う

---

## 現在の構成（セットアップ済み）

| 項目 | 値 |
|---|---|
| アカウント名 | Emo CC |
| Bot ベーシックID | @792ohjpx |
| プロバイダー | Emocute (2005200720) |
| Channel ID | 2010233158 |
| 認証情報 | `.env`（gitignore）+ Apple Notes「PWs」フォルダ |
| 反応条件 | mention_or_prefix（`Emo`/`emo`/`エモ`/`えも`/`CC` を含む発言・@メンション・DM）|
| LINE 側設定 | Webhook ON / 応答メッセージ OFF / チャット OFF / グループ参加 許可 ✓ |

### ⚠️ Cloudflare quick tunnel は URL が毎回変わる

`cloudflared tunnel --url` は再起動のたびに別の `*.trycloudflare.com` URL を発行する。
**Mac 再起動・トンネル再起動のたびに、LINE Developers の Webhook URL を貼り直す必要がある。**
（恒久運用するなら emocutelab.com の named tunnel 化を推奨 → 別途）

また QUIC が塞がれた回線では `--protocol http2` を付けないと 530 エラーになる。

### 再起動手順（Mac 再起動後など）

```bash
cd ~/Downloads/Sketches/line-bot
# 1. サーバー起動
node --env-file=.env server.mjs > server.log 2>&1 &
# 2. トンネル起動（http2 必須）
cloudflared tunnel --url http://localhost:8787 --protocol http2 > tunnel.log 2>&1 &
# 3. 新URLを確認
grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" tunnel.log | head -1
# 4. 上記 + "/webhook" を LINE Developers の Webhook URL に貼り直して「検証」
```

### アクセス権モデル（FULL_ACCESS=true）

究の指示により、ボットは「読みは全開・新規書き込み可・破壊と漏洩は不可」で動く。
`claude -p` を **cwd=Downloads** で起動し、CLAUDE.md とメモリ索引を文脈に持つ。
`guard.mjs`（PreToolUse フック）が毎ツール直前に検閲し、次を**拒否**する:

| 操作 | 可否 |
|---|---|
| Read / Glob / Grep（資料・メモリ・ファイル読み）| ✅ |
| Write（**新規パスのみ**）/ Edit（局所修正）| ✅ |
| 既存ファイルの上書き・削除 | ❌ 破壊防止 |
| Bash（シェル全般）| ❌ |
| MCP（Stripe/Supabase/メール送信等）| ❌ |
| 認証情報・鍵（.ssh/.env/.credentials 等）の Read | ❌ 漏洩防止 |
| 金関連ファイル（stripe/決済/売上/口座/請求 等）の Read | ❌ 漏洩防止 |

口調は CLAUDE.md 規約準拠（フレンドリー禁止）。`FULL_ACCESS=false` で tmp 隔離の安全モードに戻る。

### ローカル疎通テスト

```bash
node test_webhook.mjs   # 署名付き webhook を自サーバーに投げて claude 応答を確認
```
