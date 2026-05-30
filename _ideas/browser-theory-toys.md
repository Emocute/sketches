# ブラウザ理論 toy 連作（backlog）

エモスタ（Studio）のエンジン資産を、VST でもゲームでも CLI でもなく **「ブラウザで完結して音が鳴る、触れる理論 toy」** として連作する。空白地帯（既存は全部 VST / ゲーム / CLI）。各 toy は単一 HTML + Tone.js、独立フォルダ、依存ゼロ。

着手したら `Sketches/<name>/` に昇格、この行を消す。

## 第一弾（着手済）

- ✅ **voicing-lab** — 1 コードを 7 ボイシングで鳴らし比べ。`voicing.py` 哲学の web 化

## 候補（被り判定済み、上から優先）

1. **reharm-roulette** — 度数進行を入れる/プリセット選ぶ → REHARM 技（tritone sub ♭II7 / chromatic mediant ♭VImaj7 / rootless m9=maj7 / Lydian ♯11 / 3 度下行）をワンクリック適用、before/after を鳴らし比べ。`REHARM_TABLE` の web 化。
   *被り*: Harmonizer(VST 進行リハモ)とコア機能は近いが、形態（ブラウザ・度数テキスト・教育/発想・即試聴）が別。グレー→可。

2. **cliche-detector** — 進行を入れると「VIm-IV-IIm-V は手垢ループ」等を判定し、Studio の「凡庸進行禁止」基準で歪ませ案（REHARM 技 1-2 個）を返す。`anti_pattern_checker.py` 哲学の web 化。
   *被り*: なし（判定+提案 toy は既存に無い）。

3. **degree-ear-trainer** — 度数耳トレ。コードや進行を鳴らして「今のは ♭VImaj7」を当てる。Studio 度数統一表記そのまま。
   *被り*: なし（ゲームは Numbloom/Idiograph だが非音楽）。

4. **cadence-garden** — 「凡庸禁止＋REHARM 技仕込み」の非凡 8 コードターンアラウンドを毎回生成して度数+音で見せる daily 生成 toy。
   *被り*: Geomonic(進行生成 VST)とコンセプト近接。形態（ブラウザ教育 toy・MIDI 書き出しなし）で差別化。グレー。

5. **artist-dna-radar** — `ARTIST_DNA.md` の 29 名を「和声密度 / リズム / テクスチャ / Era」軸でレーダー可視化、似た音像を引き合わせる索引。
   *被り*: なし（ARTIST_DNA を読み物でなく触れる索引にするのは新規）。

6. **tension-stacker** — ルート上に 9/11/13/♭9/♯11/♭13 を 1 つずつ積んでいき、どこで「濁る/開く」かを耳で確かめる積み木 toy。voicing-lab の弟分（テンション特化）。
   *被り*: voicing-lab と近いので統合 or 後回し。
