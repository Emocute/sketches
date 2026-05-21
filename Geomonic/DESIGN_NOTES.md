# Design Notes — IV Lyd On VI 系 MIDI 生成器

> 2026-05-21 究指示「IV Lyd On VI がいい・判断は全部任せる・ツール化記録残しつつ MIDI 生成」

## 1. IV Lyd On VI とは

**スラッシュコード表記**: C major キーで `F Lyd / A` のような voicing。

- IV = F（C major の subdominant）
- Lyd = Lydian モードで響かせる
- On VI = VI 度の音をベースに置く（C major の VI = A）

→ ベース A の上に F Lydian の色（F-A-C-E-G-B-D）を載せる。

### サウンドの正体
A bass + F Lydian = **A Aeolian 上に F natural を on-top** で乗せた響き ≒ Joe Hisaishi *Always with Me* / Pat Metheny / Steely Dan の浮遊スラッシュ。具体的には:

- A2（bass）
- F3（slash の "F"、defining tone）
- A3 C4 E4（F major 7 の内声）
- G4（7th, F の M7）
- B4（**Lydian #4 of F = the floating sky-note**、ココが効く）

A bass を root と読めば `Am7 add ♭13 add 11` だが、F/A と読む方が voicing 意図に合う。Lydian #4 の B が静止音場に「浮遊感」を与える唯一の音 → Reich の "pointing out" の対象として最適。

## 2. 採用した研究結果

| 採用 | 不採用 | 理由 |
|---|---|---|
| Reich *Music for 18* 二層時間（pulse + breath） | Reich phasing | 静止 voicing に phasing は破壊的 |
| Cohn hexatonic cycle（M3 関係循環） | LCC outgoingness 全段階 | IV Lyd On VI の文脈外 |
| Lydian #4 "pointing out"（Violin Phase 系） | Xenakis sieve | スケール構築の必要なし |
| Tymoczko voice-leading 最小化 | Spectral microtuning | 標準 MIDI で再現不可 |
| Eno incommensurate breath cycles | Stockhausen formula | macro 構造はシンプル保持 |

## 3. 生成する 3 本

### A. `iv_lyd_on_vi_dwell.mid` — メイン作品

Reich *Music for 18 Musicians* の二層時間で IV Lyd On VI に 1 コード dwell。

**Voicing (C major key, F Lyd / A)**:
```
sky    B4  (71) ← Lydian #4、pointing out 対象
        G4  (67) ← M7 of F
pulse   E4  (64) ← inner pulse
        C4  (60) ← inner pulse
        A3  (57) ← inner pulse
low     F3  (53) ← slash の "F"、defining tone
bass    A2  (45) ← VI bass
```

**プロセス（80 小節 / BPM 84 ≒ 3分49秒）**:

| 小節 | レイヤー | 動き |
|---|---|---|
| 1–8 | bass + low F | A2 + F3 静かに立ち上げ、breath で長音 |
| 9–24 | + pulse | 内声 A3-C4-E4-G4 の 8th note ostinato が gradually fade in |
| 25–40 | + sky B4 | Lydian #4 が velocity 0→full で浮上 ("pointing out") |
| 41–56 | full saturation | 全層 active |
| 57–64 | sky decay | B4 が velocity full→0 で沈降 |
| 65–72 | pulse decay | inner pulse fade out |
| 73–80 | bass + low F | 開始状態に戻り fade |

**Pulse pattern (8th note ostinato)**:
```
beat   1  &  2  &  3  &  4  &
note   A3 E4 C4 G4 A3 E4 C4 G4
```
broken arp。F major 7 の内声を 8 分音符で循環。

### B. `iv_lyd_on_vi_cycle.mid` — Cohn hexatonic cycle 版

IV Lyd On VI を hexatonic cycle（M3 関係）で巡る。voice-leading 最小化（Tymoczko geodesic）。

```
key:    C    →  A♭   →   E    →   C   (一周)
slash:  F/A  →  D♭/F  →  A/C#  →   F/A
```

各キー 16 小節 dwell、key 遷移は 4 小節 cross-fade で voice-leading 最短経路。

**遷移ロジック**: 各 voicing を 7-note (F Lyd の 7 音) として、次の Lyd voicing への各音 displacement を Tymoczko の L1 距離（半音単位 displacement 総和）で最小化。

### C. `iv_lyd_on_vi_eno.mid` — Eno incommensurate loops 版

互いに素な長さのループを重ねて永遠に non-repeating な texture を作る。

| layer | length (8th) | content |
|---|---|---|
| bass | 13 | A2 long tone、息継ぎあり |
| low F | 17 | F3 long tone、 ずれた息継ぎ |
| pulse | 8 | A3-C4-E4-G4 broken arp（基本 1小節） |
| sky | 23 | B4 short attack、 sparse |
| inner echo | 19 | G4 / E4 alternating sparse |

lcm(8, 13, 17, 19, 23) = 967,304 → 数万年 non-repeating。実用 8 分間程度で十分耳に "決して同じには響かない" 感が出る。

## 4. 共通仕様

- フォーマット: SMF type 0
- BPM: 84（Music for 18 Musicians 系の breath tempo）
- 拍子: 4/4
- Velocity: dynamic envelope は手動 ramp（ベタな注入を避けるため）
- Channel: 0 のみ（DAW で楽器切替前提）
- 出力先: `output/iv_lyd_on_vi_{dwell,cycle,eno}.mid`

## 5. ツール化への伏線

将来 Rust + nih-plug VST 化する時の参照点として残す:

| 概念 | この Python 実装での所在 | VST 化時の役割 |
|---|---|---|
| Voicing spec | `IVLydOnVI` dataclass | Voicing engine struct |
| Process layer | `dwell_envelope()`, `pointing_out()`, `incommensurate_layer()` | Sequencer modules |
| Cycle path | `hexatonic_cycle()` | Progression engine |
| Voice-leading distance | `vl_distance(v1, v2)` | Transform cost function |
| SMF writer | `write_smf()` | (VST では不要、即 NoteEvent 送信) |

## 6. 既存生成器との関係

- `tools/lydian_geometry.py` の 5 本（v1）は保持。レガシー reference として残す
- 本設計は v2 という位置付け。`iv_lyd_on_vi.py` で別ファイル
- `output/lydian_*.mid` (v1) と `output/iv_lyd_on_vi_*.mid` (v2) は併存

## 7. Arc 版（2026-05-21 究指示: 2分・展開・数理徹底）

**`iv_lyd_on_vi_arc.mid`** — 40 bars @ BPM 80 = 2:00 ちょうど、8技法統合。

### 8 技法の同時運用

1. **Cohn hexatonic cycle**: tonic schedule = `C(0–16) → A♭(16–24) → E(24–32) → C(32–40)` の M3 関係循環
2. **Tymoczko VL geodesic**: 各 tonic 変化点で `best_octave_match` により ±12 補正で L1 距離最小化
3. **Reich Music for 18 二層時間**: breath layer (bass + low F、長音) + pulse layer (内声 8分音符 broken arp)
4. **Lydian #4 pointing out**: sky note を bar 12 から sparse、bar 24 peak で full velocity 85、palindrome decay
5. **Eno incommensurate**: 再アタック周期 — bass = 4 bars、low_F = 3 bars、sky = 5 bars (lcm=60 → 40 bars 内で同期しない)
6. **Russell LCC outgoingness**: bar 25 で sky note を +1 semitone (Lydian → Lydian #5)、1 bar のみ、peak の chromatic 緊張点
7. **Stockhausen formula 自己相似**: 4-bar micro cell の attack/develop/peak/release 形が、40-bar macro arc と同形 (起承転結)
8. **Reich palindrome**: bar 0–20 = 立ち上げ起承、bar 20–40 = 鏡像 decay。bass/low_F/pulse/sky すべての velocity envelope が bar 20 を中心に対称

### マクロ構造（起承転結 × Stockhausen 投影）

```
bar  0– 4  [起 立ち上げ]    bass A2 + low F3 fade in (vel 25→72)
bar  4– 8  [起 維持]        bass full, low F full, まだ pulse なし
bar  8–12  [承1 pulse 加入] inner pulse fade in (vel 0→55)
bar 12–16  [承1 sky 萌芽]   sky B4 sparse hint, vel ramp 開始
bar 16–20  [承2 hexatonic1] C → A♭ 遷移、D♭ Lyd / F に voice-leading
bar 20–24  [転1 sky 加速]   sky vel 60→85、A♭ key dwell
bar 24–25  [転2 peak]       E → A Lyd / C# に遷移、sky D#5 full、shimmer 加入
bar 25–26  [LCC +1 inflection] sky を +1 semitone (D#5 → E5、Lyd #5 = Acoustic mode)
bar 26–32  [転2 持続]       E key、sparkle layer (sky + 12) bar 22–30 にちりばめ
bar 32–36  [結 palindrome1] C key 復帰、sky decay 65→0、pulse decay 55→0
bar 36–40  [結 fade]        bass/low_F fade 72→22
```

### 美的・知覚的判断

- **2 分は Reich プロセスとしては短い**が、Stockhausen formula 圧縮で macro arc を成立させる
- **palindrome 形式が「同じ場所に戻る」感**を演出。Lydian は V→I 引力なく、palindrome と相性良い
- **Russell LCC +1 inflection は bar 25 の 1 小節のみ**。長く持つと chromaticism が支配的になり浮遊感が壊れる
- **Eno incommensurate 周期 (4/3/5)** が bar 単位の grid と微妙にずれることで、palindrome の対称性に「呼吸」を入れる

### 数理技法と聴感の対応表

| 技法 | 数学的実体 | 聴覚的に何が起きる |
|---|---|---|
| Cohn hexatonic | T_4 cyclic group (M3 trans) | 3 keys が等距離回転、戻ってくる |
| Tymoczko geodesic | T^7/S_7 上の L1 最短経路 | コード変化が荒れず滑らか |
| Reich 二層時間 | 異周期過程の重畳 | pulse と breath が独立した時間流 |
| Pointing out | velocity ramp | sky note が「いつのまにか聞こえてくる」 |
| Eno incommensurate | gcd(4,3,5) = 1 | layer の再アタックが grid 外でずれる |
| LCC inflection | Lyd → Lyd #5 半音上昇 | 一瞬の chromatic 緊張 |
| Stockhausen formula | self-similar 4↔40 | micro と macro が相似形 |
| Palindrome | 時間反転対称 | 半分聞いた所が頂点、後半が鏡 |

## 8. 評価基準（次回究フィードバック時の論点）

1. **音場として静止感があるか**（pulse が機能しすぎて忙しくなってないか）
2. **B4 sky-note の浮上が perceptible か**（pointing out が成立してるか）
3. **hexatonic cycle で voice-leading が荒れてないか**（Tymoczko geodesic 妥当性）
4. **Eno 版が "永遠に違う" 感を出してるか**（incommensurate らしさ）
5. **音楽的に Hisaishi / Metheny 系の浮遊スラッシュサウンドが出てるか**（究の本来の好み照合）
