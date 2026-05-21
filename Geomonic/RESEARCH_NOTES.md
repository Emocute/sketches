# Research Notes — Geomonic 数理 MIDI 生成器

> 2026-05-21 究の要求「綺麗でも面白くもない・既存研究を徹底的に」に応えて 3 並列調査エージェントを走らせた結果の要約。将来ツール化する時の理論側根拠としてここに保全。

## 1. Bite vs. Paper の判別基準

**音楽として生き残った技法には共通構造がある**:
1. 数理構造が**知覚不変量と結合**している（共通音保持・倍音列・位相うなり等）
2. ルールは**1つだけ**、パラメータが**1つだけゆっくり**変わる（Reich essay）
3. 出力は**決定論的だが情報的に豊か**（指定しなかった副産物 > 指定した内容）

**Paper で死んだもの**: 一次マルコフ、CA→pitch、L-system note level、voice-leading 無視の音列、ランダム pc 順列、Wolfram NKS の CA-music sketch、Cope EMI の Bach 模倣（技術的には完璧だが repeated listening されない）。

## 2. 採用候補テーブル

| 技法 | 提唱者 / 年 | コア機構 | Geomonic 適用案 |
|---|---|---|---|
| Neo-Riemannian PLR | Cohn 1996, 1997 / Hyer 1995 | P/L/R は三和音間で 2/3 共通音保持。Tonnetz の鏡像反射 | 三和音遷移の primary 制御 |
| Voice-Leading Orbifold | Tymoczko Science 2006, GoM 2011 | n音和音 = T^n/S_n 上の点。voice-leading distance = displacement sum 最短経路 = geodesic | コスト関数として |
| Xenakis sieve | Xenakis 1963/1992 | ⟨period, offset⟩ の AP 和集合で非オクターブ周期スケール。Jonchaies 1-4-1 sieve | スケール構築層 |
| DFT pc-coefficient | Quinn 2007, Amiot 2016, Yust 2017 | pc-set 特性関数の DFT、a5 高 = diatonic, a3 高 = augmented, a6 高 = whole-tone | スケール間の連続補間 |
| Spectral (Grisey) | Grisey 1975, Murail 1980 | 実音 FFT を orchestra に展開、partials-as-pitches | 倍音列ベース voicing |
| Reich phasing | Reich 1965–1972 | 同一パターン × 微小 ε 遅延、emergent stream を聴覚が抽出 | rhythm 軸 |
| Reich *Music for 18* | Reich 1976 | 11 chord cycle × breath 層 + pulse 層 二重時間、ABCDCBA palindrome | structural macro form |
| Eno incommensurate loops | Eno 1978 *Music for Airports* | 互いに素な長さのループ重ね、永遠に non-repeating | rhythm 派生 |
| Russell LCC | Russell 1953/59/01 | Lydian = 5度7積み = tonal gravity center、outgoingness 9段階 | mode hierarchy |
| Stockhausen formula | Mantra 1970, LICHT 1977–2003 | 1分メロが 16分のオペラ楽章にフラクタル展開 | macro form |

## 3. Reich のメカニクス（詳細）

### Piano Phase (1967)
- セル: `E F# B C# D F# E C# B F# D C#`（12-semiquaver、5 pc、B Dorian / E minor pent 近傍）
- 2 pianist、unison 開始 → P2 が 1/16 先まで accel → ロック
- **離散 12 位相状態を連続accelerandoで繋ぐ**。音楽的に面白いのは離散位置、連続部は遷移美学

### Violin Phase (1967) 〜 "pointing out"
- 位相を組んだ後、emergent な内部旋律を別ボイスで二重化、velocity ramp で浮上
- これが Reich の核心ギミック。「指定しなかった副産物」を可視化する装置

### Drumming (1971)
- 1パターンに対し 3 直交軸: `fill_density` × `phase_offset` × `timbre/octave`
- 各楽章で 1軸だけ動かす、他は静止 → rule audibility 保つ

### Clapping Music (1972)
- 12-unit pattern (West African 標準鐘パターン、max-evenness + 非対称)
- 1 拍/8 小節シフト × 12 回で原点復帰 = Z/12Z の純粋回転
- Colannino/Gómez/Toussaint: このパターンは emergent beat-class 性質で combinatorially unique

### Music for 18 Musicians (1976)
- 11 chord palindromic cycle、3-sharp key 軌道（A maj / F# min / E Dor / B Dor）
- 二重時間流: marimba/piano constant 8th pulse + winds/voices breath-length phrases
- 形式 ABCDCBA
- *"Pulse and harmony had become the two structural poles of his style"*

### Reich 1968 essay *Music as a Gradual Process*
> "I am interested in perceptible processes." → ルールは**聴感で追える**こと
> "Musical processes should happen extremely gradually." → 変化は**極めて緩やか**
> 隠し serialism / random algorithms は失格

## 4. Lydian × phasing の seam

**研究結果: Lydian を位相させた前例ほぼ無い**。Reich は Dorian/minor pent 軌道、#4 を意図的に避けた（#4 が tonic を不安定化、phase music の pitch field 安定要求と衝突）。In C は Lydian を通過するが phasing しない。

予測:
- root × #4 の tritone 同時打 → 最大アクセント、emergent melody が tritone 軸 pivot
- V→I 引力なし → 全 12 位相が等価安定 = phase music の理想と一致
- Lydian color tones (M3, P5, tritone, M7) が automatic に emergent layer 浮上

**判断 (2026-05-21)**: 究は IV Lyd On VI を選択。phasing は不採用に決定。理由は IV Lyd On VI の核は浮遊静止感（A bass × F-A-C-E × B sky）であり、phasing は静止を破壊する。phase seam は別途 sketch として残す。

## 5. 市場ギャップ（Geomonic positioning）

- 商用 AI は 2023–25 で audio へ全面移行（Suno/Udio/Magenta RT）→ **symbolic MIDI ニッチ空き地**
- Scaler 3 / Captain Plugins / Cthulhu 等は理論を**隠す UI**
- **PLR / pc-set / spectral / LCC / Reich-phase を primary control surface に出した plugin = ゼロ**
- 真面目作曲家層は OpenMusic / music21 / VCV Rack に流れている

**Geomonic の lane**: theory-explicit / symbolic-MIDI / post-tonal-friendly / $40–100 indie。FeelYourSound / HY-Plugins / Stochas と同棚、Scaler とは別棚。

## 6. Concrete Recommendation for MIDI-gen Engine

優先順位（musical output 優先）:
1. **Neo-Riemannian PLR walks** + **Tymoczko geodesic** for chord progressions
2. **Voice-leading distance** as cost function
3. **Xenakis sieve** for non-diatonic scale
4. **DFT pc-coefficient** for mode interpolation
5. **Spectral from real FFT** (microtuning required)
6. **Reich process** + **Eno incommensurate loops** for rhythm
7. **Russell LCC outgoingness** as scale-choice ladder
8. **Stockhausen formula** for macro structural projection

**避けるべき (primary engine としては)**: CA→MIDI、L-system note level、voice-leading 無視の serial。spice として texture に混ぜるのは OK。

## 7. 出典（主要のみ、フル URL は 3 エージェントの個別レポート参照）

- Cohn 1996 "Maximally Smooth Cycles" Music Analysis 15/1
- Cohn 1997 "Neo-Riemannian Operations" JMT 41/1; *Audacious Euphony* (Oxford 2012)
- Tymoczko 2006 "The Geometry of Musical Chords" Science; *A Geometry of Music* (Oxford 2011)
- Lewin 1987 *GMIT*
- Forte 1973 *Structure of Atonal Music*
- Quinn 2007 *General Equal-Tempered Harmony* diss.; Amiot 2016 *Music Through Fourier Space*
- Russell 1953/59/01 *Lydian Chromatic Concept of Tonal Organization*
- Xenakis 1963/92 *Formalized Music*
- Reich 1968 *Music as a Gradual Process*
- Grisey *Les Espaces Acoustiques* (1974–85)

研究エージェント生ログ: `/Users/emocute/.claude/projects/-Users-emocute-Downloads/cffd1dfd-801b-4a4d-90ff-acd6408e64ad/tool-results/{bs1zj3cfb,bal1z9u2a,bp22ofppl,b8zg2b42a}.txt`
