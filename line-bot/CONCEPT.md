# line-bot

## 目的

LINE のトークグループに「会話する仲間」として参加する Claude ボット。究＋友人＋ボットの3者で雑談できる。Discord Bot のグループ参加版を、**追加課金ゼロ**で実現する。

## なぜ無料で動くか

| 部品 | コスト | 仕組み |
|---|---|---|
| LINE Messaging API | 無料 | 返信（reply token）は無制限・無料。push は月200通制限なので reply 主体で運用 |
| Cloudflare Tunnel | 無料 | ローカル Mac を外部 HTTPS で公開する穴 |
| 応答生成 | **API課金なし** | `claude -p`（Claude Code CLI のヘッドレス実行）で Max 20x サブスク枠を消費する |

トレードオフ: Mac mini を起動しっぱなしにする必要がある（閉じるとボット停止）。

## プライバシー設計（重要）

友人もグループに入るため、**究の個人メモリ（MEMORY.md = 住所・電話・人格設定等）を絶対に漏らさない**。

- `claude -p` を **cwd=tmp スクラッチディレクトリ**で起動 → Downloads/CLAUDE.md も各PJ CLAUDE.md も読み込まれない
- `--exclude-dynamic-system-prompt-sections` で動的セクションも除外
- 検証済: ヘッドレス `claude -p` は auto-memory（MEMORY.md）を読み込まない（対話セッション限定機能）
- ペルソナ（system prompt）にも「究の個人情報は一切話すな」を明記

## 技術スタック

- Node.js（標準モジュールのみ、**依存パッケージゼロ** = `npm install` 不要）
  - `node:http` webhook サーバ / `node:crypto` 署名検証 / `node:child_process` で `claude` 起動 / グローバル `fetch` で LINE API
- `--env-file=.env`（node 20+ ネイティブ）
- Cloudflare Tunnel（named tunnel、固定サブドメイン）

## 最小スコープ（v1）

1. LINE webhook 受信 → 署名検証 → 200 即返し
2. グループ内の全発言を会話履歴に蓄積（`history.json` 永続化、発言者名付き）
3. トリガー条件（メンション or 接頭辞 or DM）を満たした時だけ `claude -p` で応答 → reply
4. 応答は短くフレンドリーなタメ口

## やらないこと（v1）

- 画像・スタンプ・音声の理解（テキストのみ）
- ツール実行（チャット専念）
- 24時間クラウド常駐（Mac 起動中のみ。常駐したくなったら Cloudflare Worker + Claude API へ昇格 = 有料）
