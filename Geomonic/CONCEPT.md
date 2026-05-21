# Geomonic v2

Studio の和声知識と数理モデルを組み合わせて、幾何学的だが和声的に綺麗な MIDI を生成する VST3 / CLAP プラグイン。

## v2 設計の骨格

**4 軸の独立 matrix**。各軸を独立に選択でき、組み合わせが一意の MIDI 生成器を定義（単射）。

| 軸 | 役割 | 候補 |
|---|---|---|
| **A. Progression** | コード進行パターン（どのコード列を通るか） | ii–V–I / I–V–vi–IV / I–vi–IV–V / 12-bar blues / Andalusian / Coltrane changes / Pachelbel / circle of fifths / modal cycle (Dorian/Phrygian/Lydian/Mixolydian) / Royal Road / kayōkyoku 黄金進行 / custom |
| **B. Transform** | 数理モデル（コード間をどう繋ぐか・どうボイシングするか） | Tonnetz（P/L/R 変換による格子歩行） / Voice Leading Orbifold（n 次元測地線） / Symmetry（3/4/6 等分円多角形回転） / Spectral（倍音列射影、√2 / φ / π 等） / PCSet（T_n / I_n / M_n 群作用） |
| **C. Rhythm** | リズム生成（いつ鳴らすか） | 4 / 8 / 16 / 32 分音符 subdivision / Euclidean(n,k) / polyrhythm (3:2, 4:3, 5:4) / shuffle / swing / triplet / dotted / probability (each step) |
| **D. Voicing** | 音高展開（どの音域でどう積むか） | close / open / drop2 / drop3 / spread / cluster / shell (1,3,7) / quartal / register low/mid/high / inversion 0/1/2/3 |

組み合わせ例:
- `ii–V–I × Tonnetz × Euclidean(8,3) × drop2`
- `12-bar blues × Orbifold × shuffle × open`
- `circle of fifths × Symmetry(4) × polyrhythm(3:2) × shell`
- `modal cycle × Spectral(φ) × probability × cluster`

## 共通パラメータ

- **Root** (0–11): 基音
- **Mode** (Major / Minor / Dorian / ...): スケールモード
- **Sync**: DAW BPM 追従、外部 Tempo override
- **Octave Range**: 出力音域
- **Velocity Curve**: ステップごとのベロシティ

## アーキテクチャ

```
DAW transport (BPM, pos_beats)
        ↓
   ┌─────────────┐
   │ Sequencer   │   ← C: Rhythm 軸が決定（次のトリガ時刻）
   └─────────────┘
        ↓ trigger
   ┌─────────────┐
   │ Progression │   ← A: 軸が決定（次のコード）
   │ State Mach. │
   └─────────────┘
        ↓ next chord (root + chord_type)
   ┌─────────────┐
   │ Transform   │   ← B: 軸が決定（コード遷移の数学的経路 + ボイシング近似）
   └─────────────┘
        ↓ pitch class set + ボイシング座標
   ┌─────────────┐
   │ Voicer      │   ← D: 軸が決定（具体的な MIDI ノート群）
   └─────────────┘
        ↓ Vec<NoteEvent>
   send_event() → DAW
```

## 技術スタック

- Rust + **nih-plug**（HarmonyScope と同じ）
- VST3 + CLAP 両対応
- GUI: 後回し（Phase 1 はパラメータ + 図形プレビューなし）
- MIDI Out: DAW の MIDI トラックへリアルタイム送信

## DAW 対応

- **Studio One** をプライマリターゲット（究本人の主 DAW）
- macOS の VST3 配置先: `/Library/Audio/Plug-Ins/VST3/Geomonic.vst3`
- インストール: `cargo xtask bundle geomonic --release` → `target/bundled/Geomonic.vst3` を symlink

## Phase 1（最小動作確認）

**Studio One で MIDI が出る状態を最優先**。

- A: I–V–vi–IV 固定（C–G–Am–F）
- B: Transform は no-op（パターン通りのコードをそのまま出す）
- C: 4 分音符固定
- D: close voicing 固定
- パラメータ: Root のみ
- GUI: nih-plug default UI（パラメータノブのみ）

→ 動作確認 → Phase 2 で軸を本物にする

## Phase 2 以降

- B 軸 Tonnetz 実装（P/L/R 変換、進行コードを格子経路に変換）
- A 軸を 5 進行に拡張、ノブで切替
- C 軸 Euclidean、shuffle 追加
- D 軸 voicing 5 種

## Phase 3

- GUI（egui）で 4 軸セレクタ + 図形プレビュー
- パターン × 数理モデルの組み合わせライブラリ（プリセット）

## V3 — Lydian × 数理モデル（未着手）

Lydian は「**倍音列に最も近い自然スケール**」（基音から 5度堆積 6回で得られる：C–G–D–A–E–B–F#）、ジョージ・ラッセル『The Lydian Chromatic Concept of Tonal Organization』(LCC) で「すべての調性の重力中心」と定義された、数理的に最も整合的なモード。これを Geomonic に組み込む。

### 新軸 E. Scale

| Scale | 構成音（C 基点） | 性格 |
|---|---|---|
| **Lydian** | C D E F# G A B | 倍音列由来、最も明るい・浮遊感 |
| **Lydian #5 (Lydian Augmented)** | C D E F# G# A B | 増5度、宇宙的・前衛的 |
| **Lydian b7 (Lydian Dominant / Acoustic)** | C D E F# G A Bb | 倍音列の理想形、ブルース寄り |
| **Lydian Diminished** | C D Eb F# G A B | LCC で第3階層 |
| **Lydian #2 #5** | C D# E F# G# A B | LCC 第4階層、極限の外向度 |
| **(参考) Ionian / Dorian / Mixolydian** | 通常モード | 比較用 |

スケール軸は全 Transform / Progression / Voicing と独立に組み合わせ可能（**5軸目** matrix）。スケール縛りはテンション選択・voicing 段階でフィルタとして効く。

### Transform 軸に追加するモデル

| モデル | エンジン |
|---|---|
| **Lydian Chromatic Order (LCC)** | 5度堆積 7音 = Lydian、8音目から12音目まで段階的に「外向度」が増す。現在の Lydian Tonic からの 5度距離で各和音を配置、距離が短いほど「内向（協和）」、長いほど「外向（不協和）」。和音生成時にユーザーが「外向度ノブ」で 0–6 を選び、対応する音群から和音を組む |
| **Lydian Tonnetz** | 既存 Tonnetz の格子を Lydian 制約付きで歩く（#4 を含む格子、F# が常時利用可能）。Lydian Tonic からの voice leading 最短経路 |
| **Lydian Spectral** | 倍音列から #11 (4倍音 × 11/8 ≒ Lydian の #4) を強調した和音生成。物理的に最も自然な #11 voicing |
| **Lydian Symmetry** | Lydian の前半 4音（C D E F#）が全音音階の半分 = 全音シンメトリーを内包。Sym6 (whole tone) との混合モード |

### Progression 軸に追加するパターン

| Pattern | 内容 |
|---|---|
| **Lydian I–II–V–IV** | I (Lydian) – II (Dorian) – V (Mixolydian) – IV (Lydian #11) のモーダル進行 |
| **LCC Vertical Stack** | Lydian Tonic から5度堆積で順次重ねる（C → CG → CGD → CGDA → ...）。和音が時間軸で「育つ」進行 |
| **Lydian Pivot Cycle** | Lydian Tonic を半音 / 全音 / 短3度 / 長3度 / 完全4度でずらす変調サイクル（Coltrane Changes の Lydian 版） |
| **Hermode Lydian** | コードチェンジごとに Lydian Tonic を再計算（各和音を最も「内向」に響かせる）。リアルタイム LCC 解析 |

### Voicing 軸に追加するモデル

| Voicing | 内容 |
|---|---|
| **Lydian Pentachord** | 1–2–3–#4–5（Lydian の前半5音）を低音から積む |
| **Lydian #11 spread** | root – 3 – 5 – 7 – 9 – #11 – 13 の完全 Lydian テンション堆積（7和音上） |
| **Quartal Lydian** | 完全4度 + 増4度の混合堆積（McCoy Tyner 風 + Lydian の #4） |

### GUI 拡張

- Scale セレクタ追加（5軸目）
- 幾何プレビュー: **Lydian Chromatic Spiral**（Lydian Tonic を中心に5度螺旋で12音配置、現在和音の外向度を色で可視化）
- LCC「外向度メーター」（0–6 の縦バー）

### 着手前メモ

- LCC は「正しい使い方」が議論を呼ぶ理論（ラッセル本家の運用 vs マイルス周辺の解釈）。**Geomonic では「数理モデルとしての美しさ」優先**、ラッセル運用には準拠しない
- Lydian は「明るすぎ」「ふわふわしすぎ」と感じる用途では使いにくい → Scale 軸で Lydian b7 / Ionian にすぐ切替できる UX を優先
- V3 着手タイミングは V1+V2 を実 DAW で触って軸の使い心地を確かめてから（spec を実用に合わせて削る or 増やす）

### 関連参考

- George Russell『Lydian Chromatic Concept of Tonal Organization』(1953/2001 改訂版)
- Lydian は HarmonyScope の scale suggestion でも頻出 — 解析側と生成側で同じ理論基盤を共有可能

## 関連

- HarmonyScope（解析側） — 和声理論基盤を共有可能
- Harmonizer（リハーモナイズ） — 出力 MIDI を Harmonizer に食わせる遊びも
- ios_theory_lab_app（memory 構想） — モバイル版の祖型

## 配置

- フォルダ: `Downloads/Sketches/Geomonic/`
- repo: `Emocute/sketches` モノレポ subdir として開始
- 大型化したら `Downloads/Geomonic/` + `Emocute/geomonic` 独立 repo へ昇格
