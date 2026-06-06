# yay_music_bot — CONCEPT

## 目的

Yay 通話に常駐する**純音楽BOT**。将来サブスク提供を見据えた、機能を絞った優秀な音楽再生 bot。
`yay_bot`（究の個人用フル機能bot：人格/会話/TTS/聴取/録音/開発ツール込み）とは**完全独立**の別 PJ。

## スコープ（やること）

- Yay 通話への自動参加（待ち受け→creds 取得→Agora join）
- YouTube 音源の再生（yt-dlp で解決 → Agora RTC に publish）
- キュー（追加/一覧/削除/並べ替え/自動送り）
- 再生制御（スキップ/停止/一時停止/再開/音量/一曲ループ）
- システム音声配信（/live、DJ 用途）
- スラッシュコマンド + 自然言語（「○○かけて」）。**通話の全員が操作可**（サブスク客が使う前提）

## やらないこと（yay_bot に残す機能）

- 会話 / 人格（zundamon 等）/ LLM 返信 / 自発おしゃべり
- 読み上げ（TTS / VOICEVOX）/ 聞き取り（whisper）
- 通話録音
- ファイル/Bash 等の開発ツール（客に渡すと情報漏洩＝危険なので持たない）

## 技術スタック

- Node（Playwright headless Chromium で `agora_client.html` を駆動 → Agora RTC/RTM 直結）
- Python venv（yaylib）で Yay 公式 API からトークン/通話creds取得（`yay_api.py`）
- yt-dlp（`lib/music_agora.mjs`、リアルタイム stream 中継）

## 主要ファイル

- `bot.mjs` — メインループ（join + コマンド + キュー + 自動送り）
- `config.mjs` — 設定（ポーリング等）
- `lib/agora.mjs` + `agora_client.html` — Agora 参加・音楽 publish・RTM
- `lib/music_agora.mjs` — yt-dlp 解決・stream 中継
- `yay_api.py` + `.venv` — トークン/creds 取得
- `relogin.sh` + `scripts/` — トークン再取得（X ログイン1クリック）
- `run.sh` — 起動（tmux: yay_music_bot）

## 起動

```
./run.sh                 # token 確認 → tmux で bot 起動
tail -f /tmp/yay_music_bot.log
tmux kill-session -t yay_music_bot && pkill -f 'node bot.mjs'   # 停止
```

## 事業化の方針（2026-06-06 究決定: Yayで小規模運用）

- 当初ホスト型SaaSを検討したが、Yay ログイン=「Xで続ける」=Xアカ紐付けで、複数アカ化は X垢量産
  ＝Yay/X両方の規約違反＆BAN祭りの的。捨てメアド量産も不可。→ **大規模SaaSは保留**。
- 方針: **Yay で小さく運用**（実垢＋少数の実アカのみ、垢ファーミングなし）。事業化は限定的に。
- 小規模運用の土台は実装済（アカ別 token 切替 `yay_api.py` env + `fleet.sh`/`accounts.json`、実アカ2〜3個まで）。
- 手動小規模提供の手順 → **`docs/OPERATE_SMALL.md`**（`serve.sh` で友達の通話にbot投入 / Model A/B）。
- 大規模設計メモ（保留）→ `docs/ARCHITECTURE_SAAS.md`。課金は究GO必須で未着手。

## 既知の制約（サブスク事業化の前提課題）

- **1アカウント＝同時1通話**。1つの Yay アカウントでは複数の通話を同時に捌けない＝スケールしない。
  多客同時対応には bot アカウントの複数化 or 別アーキテクチャが必要。
- **Yay ToS / 非公式接続**。Agora を解析したトークン直結のため、bot/自動化が ToS 違反の可能性。
  課金して他人に売る場合は BAN・法的リスクが上がる。事業化前に要検討。
- 課金・決済の実装は未着手（究の明示GO必須、§ 課金ルール）。

## 履歴

- 2026-06-06: yay_bot から分離・新設。純音楽（YouTube）に機能を絞った独立 PJ として起票。
