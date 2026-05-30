# Reharm Roulette

ブラウザ単一 HTML の「リハモ・ルーレット」。度数進行を入れる（or プリセット）と、Studio の `REHARM_TABLE` が持つ特殊技をワンクリックで適用し、**before / after を鳴らし比べる**。凡庸進行を入れると「手垢ループ」と判定して自動で歪ませる「ガチャ」ボタン付き。

## 目的

Studio の制作哲学「凡庸進行禁止・REHARM 技を最低 1-2 個仕込め」を、誰でも耳で確かめられる toy にする。`reharm_loop.py` / `anti_pattern_checker.py` の知見の web 化。

## 搭載する REHARM 技（度数ベース）

| 技 | 変換 | 例 |
|---|---|---|
| Tritone sub | dom7 → ♭5 上の dom7 | V7 → ♭II7 |
| Backdoor | dom7 → 全音下の dom7 | V7 → ♭VII7 |
| Chromatic mediant | maj7/min → ±3/±4 半音の同型 | Imaj7 → ♭VImaj7 |
| Lydian ♯11 | maj7 → maj7♯11 | IVmaj7 → IVmaj7♯11 |
| ii–V 挿入 | ターゲット前に ii–V を差す | … → IIIm7 ♭VI7 → … |
| 3 度下行連鎖 | ルートを短 3 度ずつ下げる | Imaj7 → ♭VImaj7 → IVmaj7 |

## 既存との被り回避

- Harmonizer（VST 進行リハモ）とコア機能は近接するが、**形態が別**：ブラウザ完結・度数テキスト入力・教育/発想・即試聴。DAW へ MIDI を出さない。
- voicing-lab（toy 連作の弟）とは姉妹：あっちは「1 コードの積み方」、こっちは「進行の歪ませ方」。

## 技術スタック

- 単一 `index.html`、Tone.js CDN のみ
- 度数表記 Studio v7 準拠（メジャースケール度数）、キーは C major で発音
- コード/度数定義は voicing-lab と共有せず自前ミラー（Sketches 規約 3）

## 最小スコープ（v1）

1. 度数進行パーサ（`IIm7 V7 Imaj7` 形式 + 凡庸プリセット）
2. 各 REHARM 技ボタン → after 進行を生成し 2 段表示
3. 「ガチャ（自動で歪ませる）」= 凡庸判定 + 技 1-2 個ランダム適用
4. before / after をそれぞれ Tone.js で再生・比較
