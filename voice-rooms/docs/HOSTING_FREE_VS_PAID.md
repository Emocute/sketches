# voice-rooms — 無料の限界 / 有料で広がる所（2026-05 調査）

ブラウザ完結の匿名グループ通話（Node+ws シグナリング + WebRTC mesh + STUN）を実運用する際の、無料でどこまで行けるか・有料なら何がいくらで解けるかを4軸で調査した結論。価格は2026年5月時点。

## 結論（最短の勝ち筋）

1. **今すぐ無料で公開** … `cloudflared` quick tunnel（一時URL・アカウント不要）。← 現在この状態。
2. **無料で恒久公開** … 究の `emocutelab.com` で **Cloudflare named tunnel** を張り `voice.emocutelab.com` に割当（追加費用ゼロ）。Mac 起動中のみ稼働。
3. **Mac 非依存で常時公開（無料枠）** … シグナリングを **Cloudflare Workers + Durable Objects**（スリープ無し・WS Hibernationでアイドル無課金）へ移植。要・Node→Workers 書き換え。
   - 書き換えを避けて最速で出すなら **Render Free**（コード改変ゼロ、ただし15分無通信→復帰1分のコールドスタート）。`render.yaml` 同梱済み。
4. **接続性（重要）** … STUN だけだと対称NAT/モバイル/企業網で **15〜25% が接続失敗**。**Cloudflare Realtime TURN（無料1,000GB/月）** を iceServers に足すだけで救済できる。実装済みの `/ice` に鍵を差すだけ（下記）。
5. **スケール** … mesh は音声で実用 **〜6人程度**。18人規模なら **SFU**（Cloudflare Realtime SFU / LiveKit）へ。プロト段階は不要。

## 軸別サマリ

### ① ホスティング & シグナリング常駐
| 選択肢 | 無料の中身 | 制限 | 有料 |
|---|---|---|---|
| **Cloudflare Workers + Durable Objects** ★本命 | 静的配信(無料無制限)+WS常駐、スリープ無し、WS Hibernationでアイドル無課金、独自ドメイン無料 | 現 Node+ws を Workers+DO へ書き換え要。10万req/日・WS受信20:1課金 | $5/月で日次上限撤廃 |
| **Render Free** ★最速 | 現コードそのままデプロイ・HTTPS付き | 15分idleでスリープ→復帰1分。750h/月 | Starter $7/月で常時起動 |
| Deno Deploy | WS標準対応・エッジ常駐 | Deno向け書き換え要 | 従量 |
| Fly.io / Glitch / Railway | — | Glitch終了済・Fly無料枠消滅・Railwayは$5トライアルのみ | $2〜5/月 |

### ② 接続性（STUN/TURN）
- STUN（現状の Google 公開STUN）= アドレス発見のみ・無料無制限。**対称NAT等で15〜25%失敗**。
- **Cloudflare Realtime TURN** … 毎月 **1,000GB 無料**、超過 $0.05/GB（egressのみ）。サーバ運用不要。← 無料枠最強。
- 自前 coturn on Hetzner CX23（€3.49/月・20TB込）= 帯域単価が圧倒的に安い（中規模向け）。Oracle Always Free(10TB)は実質0円だが可用性不安定。
- Twilio $0.40〜0.60/GB・Metered/Xirsys 無料500MBのみ＝この規模では割高。

### ③ スケール（mesh → SFU）
- mesh は人数で帯域が N² に増える。音声のみで実用上限 **〜6人**。
- 18人（Yayのグループ上限）狙いは SFU 必須：Cloudflare Realtime SFU / LiveKit Cloud(無料枠+従量) / mediasoup(self-host)。プロト段階は未着手で可。

### ④ 常設の公開URL
- **Cloudflare named tunnel**（無料）… `voice.emocutelab.com` を Public Hostname で割当、DNS自動生成・追加費用ゼロ。WebRTC音声はトンネルを通らずP2P直結なので影響なし。
- 濫用対策（無料枠）… 匿名公開のまま **WAF rate limit 1ルール + Turnstile**、招待制βなら **Cloudflare Access（Zero Trust Free 50ユーザー・ソーシャルログイン）**。
- 常時稼働を Mac 依存から外すなら $4〜6/月のVPSで cloudflared 常駐（課金は要GO）。

## このコミットで実装済み（無料・自走）
- **WSハートビート（25秒 ping/pong）** … Cloudflare等の ~100秒 idle切断で沈黙中にシグナリングが落ちる問題を解消（`server.js`）。クライアント側も25秒キープアライブ。
- **`/ice` エンドポイント** … STUN常時返却。`TURN_URLS`/`TURN_USERNAME`/`TURN_CREDENTIAL` を環境変数に入れると TURN を返す（鍵をクライアントに焼かない）。クライアントは起動時に `/ice` を取得しフォールバックはSTUN。
- **`render.yaml`** … Render Free へワンクリックデプロイ用ブループリント（health check=`/ice`、東京近傍リージョン）。

## 次の一手（究のGO/操作が要る＝本番アカウント・DNSに触る）
A. **恒久URL（無料・最有力）**: `voice.emocutelab.com` を named tunnel 化
   ```
   cloudflared tunnel login            # ブラウザで究の Cloudflare 認証（究が実行）
   cloudflared tunnel create voice-rooms
   cloudflared tunnel route dns voice-rooms voice.emocutelab.com
   cloudflared tunnel run --url http://localhost:8800 voice-rooms
   ```
B. **Mac非依存で常時無料**: GitHub へ push → Render で Blueprint デプロイ（`render.yaml` 使用）。
C. **接続成功率を上げる（無料1000GB）**: Cloudflare Realtime TURN のキーを発行し、ホストの env に `TURN_URLS/USERNAME/CREDENTIAL` を設定（`/ice` が自動で配る）。

価格・無料枠は調査時点（2026-05）の各社公式値。TURN無料1,000GB・$0.05/GB、Render Free 750h/15分スリープ、Workers $5/月は公式確認済み。
