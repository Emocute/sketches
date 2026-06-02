# yay_bot

Yay（yay.space）の通話チャットに Emocute の Claude「EmoCC」を常駐させ、究といつも話す調子で会話に返信する。さらに別ブラウザの YouTube/Spotify を BlackHole 経由で通話に流せる（DJ）。設計・調査結論は `CONCEPT.md`。

## アーキテクチャ

```
[Yay Chrome  profile-yay  CDP:9222] ──CDP── bot.mjs (tmux)
   通話チャット(DOM読/投稿)              │ 新着→ claude -p (中立cwd) → 投稿
   マイク入力 = BlackHole 2ch            │
[Vivaldi  profile-music  CDP:9223] ──CDP─┘ 音楽: /play→Spotify /yt→YouTube
   setSinkId → BlackHole 2ch ─(loopback)→ マイク → 通話/究へ
```
- **チャットは DOM 経由が唯一解**（通話チャットは Agora RTM 暗号化バイナリで API 不可。詳細 CONCEPT.md）。
- ブラウザは**デバッグ口付き起動 → connectOverCDP**（窓を閉じない・ロック衝突なし）。
- `claude -p` は中立ディレクトリ実行（リポジトリ CLAUDE.md を読ませず思考漏れ防止）。

## 構成

| パス | 役割 |
|---|---|
| `run.sh` | 一括起動（ブラウザ冪等 + bot を tmux 起動） |
| `stop.sh` | bot 停止（`--all` でブラウザも） |
| `bot.mjs` | メインループ（ポーリング→返信→/play） |
| `config.mjs` | プロファイル/間隔/連投ガード/セレクタ/自分のuser id |
| `lib/yay.mjs` | Yay トランスポート（CDP・読/投稿・パネル開閉） |
| `lib/claude.mjs` | EmoCC 返信生成（claude -p・255字制限・素のClaude調） |
| `lib/music.mjs` | Vivaldi 再生 + setSinkId→BlackHole |
| `scripts/launch_yay.sh` | Yay Chrome 起動(9222・冪等) |
| `scripts/launch_music.sh` | Vivaldi 起動(9223・冪等) |
| `scripts/setup_audio.mjs` | 通話マイク=BlackHole + ミュート解除 |
| `scripts/build_icons.mjs` | アバター生成ユーティリティ |
| `scripts/_debug/` | 調査・テスト用の使い捨て（参考保管） |

## 使い方

### 初回だけ（手動）
1. `~/.claude/playwright-profile-yay` で Yay にログイン（`scripts/launch_yay.sh` で窓を開く）。
2. `~/.claude/playwright-profile-music`（Vivaldi）で Spotify にログイン（`scripts/launch_music.sh`）。
3. BlackHole 2ch 導入済み（`brew install --cask blackhole-2ch`）。

### 毎回
1. Yay で **Emo Claude として通話に参加**（手動）。
2. `./run.sh` … ブラウザ確認＋bot を tmux 起動。
3. 音楽も流すなら `node scripts/setup_audio.mjs`（通話参加後に1回／マイク=BlackHole+解除）。
4. 停止: `./stop.sh`（通話も終わるなら `./stop.sh --all`）。

### チャットコマンド
- `/play <曲>` → **YouTube 既定**（`<video>` で `setSinkId` が確実に効く＝最優先）
- `/yt <曲>` → YouTube（`/play` と同じ）
- `/sp <曲>` → Spotify（Premium=広告ゼロ。ただし Widevine DRM で `setSinkId` が弾かれ得る＝流れない時は `/play` に切替）
- `/stop` `/pause` → 停止

**自動化**：`/play` を打つと bot が再生前に「通話マイク=BlackHole＋ミュート解除」を自動で保証する（究が `setup_audio.mjs` を手で叩く必要なし）。再生後、bot がチャットに「通話へ流れてる」or「どこで経路NGか」を返す。

## 音が流れない時（診断）
- `node scripts/diag_audio.mjs` … 通話参加中に叩くと、経路の各リンクを ✓/✗ で表示（OS の BlackHole → Vivaldi の setSinkId → 通話マイク入力 → ミュート解除）。**✗ が出てる場所＝音が止まってる場所**。
- 究自身のスピーカーでも聞きたい → Audio MIDI設定で**複数出力装置**（BlackHole 2ch＋スピーカー）を作り「**Yay出力**」と命名すると、`config.mjs` の `sinkPrefer` が自動でそれを優先（通話＋自分の耳の両方に出る）。

## 運用メモ
- ログ: `tail -f /tmp/yay_bot.log`
- bot は `seen` を `state.json` に永続化 → 再起動してもメッセージを取りこぼさない。
- 課金 NEVER（Spotify Premium は既契約）。`.yay_token` 等の認証ファイルは gitignore。
