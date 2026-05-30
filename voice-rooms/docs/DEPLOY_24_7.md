# 24時間公開（Cloudflare Workers + DO）— 再開手順

無料・スリープ無し・Mac非依存で `voice.emocutelab.com` に常時公開する。コード移植は完了済み（`worker/`）。残りはデプロイのみで、唯一 **wrangler ログイン（ブラウザ・究本人）** だけ手動。

## 残りステップ
1. ログイン（究が1回・ブラウザで Cloudflare 認証）:
   ```
   cd Sketches/voice-rooms/worker
   npx wrangler login
   ```
2. ↑が済んだら Claude に伝える。以降は Claude が自走:
   - `npx wrangler deploy`（Worker + Hub DO + `voice.emocutelab.com` の DNS/証明書を自動発行）
   - 鍵を secret 化: `printf '%s' "$(cat ~/.cloudflared/vr_gate_pass)" | npx wrangler secret put GATE_PASS`（既存の鍵を流用＝Apple Notes/PWs の値のまま）
   - 到達確認（鍵ページ→鍵→入室、2タブで通話）

## 構成
- `worker/src/index.js` … Worker（鍵ゲート / `/ice` / 静的配信）＋ Hub Durable Object（全ルーム＋全接続のシグナリング。旧 `server.js` ロジック移植、SQLite-backed DO で無料枠対応）
- `worker/wrangler.toml` … assets(run_worker_first) / DO binding / `voice.emocutelab.com` custom domain / migrations(new_sqlite_classes)
- `worker/public/index.html` … クライアント（`public/index.html` のコピー。WS は同一ホスト、`/ice` 取得、鍵 cookie 対応）

## 今ライブな状態（移行前）
- `https://rooms.emocutelab.com` … Mac + tmux(`vr`) の Node サーバ + cloudflared named tunnel。**鍵ゲート有効**（パスフレーズ＝Apple Notes/PWs）。**Mac起動中＋tmux生存中のみ**稼働。
- Workers 版が動いたら、こちらの tunnel(`rooms`) は停止して `voice`(Worker・24h) に一本化する。

## 注意
- Worker 版の鍵は `wrangler secret put GATE_PASS`。未設定だと**ゲート無効＝公開**になるので、deploy 後に必ず secret を入れる（手順2に含む）。
- DO は1インスタンス集約（mesh前提の小〜中規模で十分）。多人数化は将来 SFU（`docs/HOSTING_FREE_VS_PAID.md` 参照）。
