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

## 関連

- HarmonyScope（解析側） — 和声理論基盤を共有可能
- Harmonizer（リハーモナイズ） — 出力 MIDI を Harmonizer に食わせる遊びも
- ios_theory_lab_app（memory 構想） — モバイル版の祖型

## 配置

- フォルダ: `Downloads/Sketches/Geomonic/`
- repo: `Emocute/sketches` モノレポ subdir として開始
- 大型化したら `Downloads/Geomonic/` + `Emocute/geomonic` 独立 repo へ昇格
