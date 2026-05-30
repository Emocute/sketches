# Chord Forge

唸るコード進行を量産して、Pianoteq で鳴らして聞ける機構。

## 目的

エモスタ（Studio v7）の和声知識を総動員して、手垢のついていない・理論的に強いコード進行を
カタログとして大量に持ち、度数 → ボイスリーディング最適化 → MIDI → Pianoteq レンダ → ブラウザで聴き比べ、
までを一発で回す。「とりあえず良いコード進行を浴びたい」時の蛇口。

## 技術スタック

- **和声エンジン**: `Studio/tools/harmony_utils.py` を直接 import（複製しない＝真の総動員）
  - `auto_voice_lead` でボイスリーディング最適化、`insert_secondary_dominants` / `generate_tritone_substitutions` でリハーモ増殖
- **MIDI 書き出し**: 依存ゼロの自前 SMF type-0 writer（`forge.py` 内蔵）
- **音源**: Pianoteq 9 CLI（`--headless --preset ... --midi ... --wav ...`）でオフライン WAV 書き出し
- **試聴**: 生成した `index.html` を Chrome で開く（`<audio controls preload="none">` ＝ Studio 許可形、自動再生なし）

## 最小スコープ

```bash
python3 forge.py all                 # カタログ全部を C で MIDI 化 → Pianoteq レンダ → index.html → Chrome
python3 forge.py list                # カタログ一覧（進行名・度数・技法）
python3 forge.py make --id marunouchi --key F   # 1 進行だけ、キー指定
python3 forge.py make --reharm                  # Studio の変換でリハーモ版も増殖
```

## V2 — 複雑進行の延々量産（forge_v2.py）

V1 の手選びカタログ（邦楽王道＋基本ジャズ）とは被らない上級技法を**アルゴリズム生成**で延々作る。

技法ジェネレータ9種: ネオ・リーマン(PLR)変換 / オクタトニック軸 / ヘキサトニック(増三和音系) /
コルトレーン・マトリクス(長3度3トニック) / ドミナント・バックサイクル / コンスタント・ストラクチャー(平行移動) /
ポリコード上部構造 / ネガティブ・ハーモニー(軸鏡映) / サイドスリップ(半音プレーニング)。

- **複雑度足切り**: Studio の `progression_complexity_score` で 65 未満は捨てる（rich/complex のみ残す）
- **重複排除**: 移調不変シグネチャ（tonic を 0 に正規化）で V1 とも過去生成とも被らせない。`v2/seen.txt` に永続化、再起動越え
- **二重起動防止**: `v2/endless.lock`（PID ロック）
- **ディスク保護**: 空き 8GB 未満で自動停止

```bash
python3 forge_v2.py once --n 12          # テスト生成（レンダなし）
python3 forge_v2.py endless --render      # 延々生成＋Pianoteq レンダ（tmux で回す）
python3 forge_v2.py page --open           # index_v2.html（直近400・新しい順）を Chrome で
```

tmux 運用:
```bash
tmux new-session -d -s chordforge 'cd <ここ> && exec python3 forge_v2.py endless --render >/dev/null 2>&1'
tmux attach -t chordforge      # 様子を見る（Ctrl-b d でデタッチ）
tail -f v2/run.log             # 進捗ログ
tmux kill-session -t chordforge   # 停止
```

出力: `v2/midi/`・`v2/wav/`・`v2/catalog.jsonl`（メタ）・`index_v2.html`（10個ごと自動再生成）。

## 規約継承

- `Sketches/CLAUDE.md` / `Downloads/CLAUDE.md`（応答・ファイル操作・コミット規約）を継承
- **音を鳴らさない**: WAV はオフライン書き出しのみ。`afplay`/autoplay 禁止（Studio 累犯項目）。聴くのは究がブラウザで
- 度数表記はメジャースケール準拠（I=0, II=2, III=4, IV=5, V=7, VI=9, VII=11）

## 依存

- `Studio/tools/harmony_utils.py`（兄弟 PJ。無ければ即 raise、fallback しない）
- Pianoteq 9（`/Applications/Pianoteq 9/...`。無ければ MIDI まで生成して警告）
