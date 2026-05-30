# ブラウザ理論 toy 連作（backlog）

エモスタ（Studio）のエンジン資産を、VST でもゲームでも CLI でもなく **「ブラウザで完結して音が鳴る、触れる理論 toy」** として連作する。空白地帯（既存は全部 VST / ゲーム / CLI）。各 toy は単一 HTML + Tone.js、独立フォルダ、依存ゼロ。

着手したら `Sketches/<name>/` に昇格、この行を消す。**public repo（Emocute/sketches tracked）なのでアーティスト名 taxonomy 固定は使わない**（CLAUDE.md 監査ルール）。

## 実装済み（11 本）

- ✅ **voicing-lab** — 1 コード × 7 ボイシング比較
- ✅ **reharm-roulette** — REHARM 技 6 種＋凡庸判定＋ガチャ
- ✅ **circle-of-fifths** — 五度圏プレイグラウンド
- ✅ **mode-mixer** — 7 旋法弾き比べ
- ✅ **negative-harmony** — 鏡映変換で裏進行
- ✅ **tension-stacker** — テンション積み木＋濁り計
- ✅ **euclid-rhythm** — Bjorklund リズム生成
- ✅ **chord-scale-mapper** — コード → スケール対応
- ✅ **interval-ear-trainer** — 音程耳トレ
- ✅ **groove-swing** — swing 量の連続可変
- ✅ **cadence-lab** — 終止形の弾き比べ

## 次の候補（被り判定済み、上から優先）

1. **chromatic-approach** — ターゲット音への半音アプローチ／囲み込み（enclosure）をベースラインで可視化・発音。被りなし。
2. **degree-ear-trainer** — 進行を鳴らして「今のは ♭VImaj7」を当てる度数耳トレ。reharm の理論を逆向きに。被りなし。
3. **voice-leading** — 2 コード間のボイスリーディング最短経路を線で可視化。Geomonic(VST)と別形態。被りなし。
4. **polyrhythm-lab** — 3:4 / 5:4 等のポリリズムを 2 リング重ねて発音。euclid-rhythm の発展。被りなし。
5. **drop-builder** — リズム＋和声を合体し、8 小節の bed を組んで書き出し（WAV/MIDI）。大型化したら `Downloads/` 昇格候補。
6. **scale-finder** — 数音を鳴らす/選ぶと、それを含むスケール候補を逆引き。chord-scale-mapper の逆向き。被りなし。
7. **hub** — 全 toy を 1 ページに集約するインデックス（連作が増えたら）。

## 設計メモ（連作共通の型）

- 配色: `--bg:#0e0e12 / --accent:#c9a86a / --accent2:#6a9ec9`（ダーク＋ゴールド）で統一
- 度数表記は Studio v7 準拠（I=0 II=2 III=4 IV=5 V=7 VI=9 VII=11）
- 発音は `Tone.PolySynth(triangle)`、volume −11〜−12、再生禁止ルールはブラウザ内ユーザー操作なので対象外
- コア計算ロジックは `node -e` で必ず単体検証してから commit
