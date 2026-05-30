# Sketches

Emocute の「思いつき開発」集積場。小ネタ・実験・遊びの PJ をここに溜める。

## 構造

```
Sketches/
├── _ideas/          ← 実装前のアイデアメモ（md ファイルで雑に溜める）
├── <PJ名>/          ← 着手したサブ PJ（フォルダ単位で独立）
│   └── CONCEPT.md   ← そのサブ PJ のコンセプト・設計メモ
└── README.md
```

## 運用

- アイデアだけ思いついた → `_ideas/<topic>.md` で雑に書く
- 実装に着手する → `Sketches/<PJ名>/` フォルダを切る、`CONCEPT.md` を最初に書く
- 大型化した → `Downloads/<PJ名>/` 直下に昇格 + 独立 repo 化（HarmonyScope / Numbloom / Harmonizer と同じ昇格パス）

## リポ

`Emocute/sketches` モノレポ。サブ PJ は subdir として共存。昇格時は `git subtree split` で独立 repo へ。

## 現在の住人

- **Geomonic** — Studio の和声知識と数理モデル（Tonnetz / Voice Leading Orbifold / 等分円 / Spectral / PC-Set）を組み合わせた MIDI 生成 VST3/CLAP
- **voicing-lab** — ブラウザ単一 HTML の「ボイシング実験室」。1 コードを Close / Drop2 / Drop3 / Rootless / Quartal / Shell / Spread で鳴らし比べ（Tone.js）。Studio `voicing.py` 哲学の web 化。理論 toy 連作の第一弾
- **emocute-toolkit** — 販売/運用の統一 CLI（監査・version bump・CHANGELOG 自動化等）
- **line-bot** — LINE グループ参加ボット（`claude -p` ヘッドレス実行）
