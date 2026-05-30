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
- **emocute-toolkit** — 販売/運用の統一 CLI（監査・version bump・CHANGELOG 自動化等）
- **line-bot** — LINE グループ参加ボット（`claude -p` ヘッドレス実行）

### ブラウザ理論 toy 連作（単一 HTML + Tone.js、依存ゼロ、エモスタのエンジン哲学を web 化）

- **voicing-lab** — 1 コードを Close / Drop2 / Drop3 / Rootless / Quartal / Shell / Spread の 7 種で鳴らし比べ
- **reharm-roulette** — 度数進行に REHARM 技 6 種を適用、凡庸判定＋🎲ガチャで自動的に歪ませ、before/after 試聴
- **circle-of-fifths** — 五度圏 SVG、キークリックでダイアトニック和音を順に発音、平行短調/近親調表示
- **mode-mixer** — 同トニックで 7 旋法を切り替え、特徴音ハイライト、明→暗の並び
- **negative-harmony** — トニック–ドミナント軸でコードを鏡映、裏の進行を生成して聴き比べ
- **tension-stacker** — 7th コアにテンションを 1 つずつ積み、濁り計＋スイートスポット判定
- **euclid-rhythm** — Bjorklund E(k,n) で 2 トラック生成、ステップ円可視化＋ループ再生

連作の backlog: `_ideas/browser-theory-toys.md`
