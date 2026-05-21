# Geomonic

幾何学的だが和声的に綺麗な MIDI を生成する VST3 / CLAP プラグイン。Studio の和声知識と数理モデルを組み合わせる。

## コンセプト

「図形で和音を動かす」。トポロジー・群論・倍音物理から導かれた "響きが必ず綺麗な" 経路上を、幾何学的に歩く。

## モード（全部盛り、切替式）

| Mode | エンジン | UI 入力 |
|---|---|---|
| **Tonnetz** | P / L / R 変換による三角格子歩行 | 三角格子上の軌道描画 or 方向ノブ |
| **Orbifold** | n 次元和音空間（Tymoczko）測地線移動 | 開始 / 終了和音指定、自動補間 |
| **Symmetry** | 3 / 4 / 6 等分円 + 多角形回転（Coltrane Changes, dim, whole tone） | 等分数 + 回転速度 |
| **Spectral** | 基音倍音列から非整数倍位置（√2, φ, π 等）を射影 | 基音 + 射影定数選択 |
| **PCSet** | T_n / I_n / M_n 群作用による pitch-class set 変換 | Forte 番号 + 変換チェイン |

## 共通パラメータ

- Root（基音）
- Rhythm Pattern（トリガパターン）
- Octave Range
- Velocity Curve
- Voicing: close / open / drop2 / drop3
- Sync: DAW BPM 追従、1/4 1/8 1/16 1/32 trigger

## 技術スタック

- Rust + **nih-plug**（HarmonyScope と同系、ノウハウ再利用）
- VST3 + CLAP 両対応
- GUI: egui or iced（HarmonyScope と揃える）
- MIDI Out: DAW の MIDI トラックへリアルタイム送信

## 出力

- リアルタイム MIDI（DAW で録音）
- 任意機能: "Capture last N bars → drag MIDI clip"（後回し可）

## 最小スコープ（Phase 1）

1. nih-plug minimal template で MIDI 出力する空 VST3 を起こす
2. Tonnetz モードだけ実装（一番 "幾何学 × 綺麗" の象徴）
3. DAW で音を出す → 設計検証

## Phase 2 以降

- Orbifold → Symmetry → Spectral → PCSet の順で追加
- GUI の幾何ビジュアライザ（軌道を実時間で描画）

## 関連

- HarmonyScope（解析側） — 同じ和声理論基盤を共有可能
- Harmonizer（リハーモナイズ） — 出力 MIDI を Harmonizer に食わせる遊びも
- ios_theory_lab_app（memory 構想） — モバイル版の祖型として転用可能

## 配置

- フォルダ: `Downloads/Sketches/Geomonic/`
- repo: `Emocute/sketches` モノレポ subdir として開始
- 大型化したら `Downloads/Geomonic/` + `Emocute/geomonic` 独立 repo へ昇格
