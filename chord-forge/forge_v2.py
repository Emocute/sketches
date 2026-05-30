#!/usr/bin/env python3
"""chord-forge V2 — さらに複雑な進行をアルゴリズム生成で延々量産。

V1（forge.py の手選びカタログ：邦楽王道＋基本ジャズ）とは被らない上級技法を
プログラム生成し、複雑度スコアで足切り、移調不変シグネチャで重複排除して
延々と新規進行を吐き続ける。MIDI → Pianoteq WAV → index_v2.html。

技法ジェネレータ:
  neo_riemannian   PLR 変換の最大平滑ボイスリーディング鎖
  octatonic        短3度軸のドミナント／減和音サイクル＋裏コード
  hexatonic        増三和音システムのクロマティックメディアント鎖
  coltrane_matrix  長3度3トニック × 各 II-V-I
  backcycle        5度圏を遡るドミナント連鎖（拡張ドミナント）
  constant_struct  単一複雑クオリティの平行移動（コンスタントストラクチャー）
  polychord        ベース上の上部構造トライアド列
  negative_harmony 機能進行のトニック-ドミナント軸鏡映
  side_slip        半音横滑りプレーニング
  modulation_journey 4〜7キーを実在の転調技法で渡る「転調の旅」（composer.py のパレット）

使い方:
  python3 forge_v2.py once  --n 12        # テスト: 12 個だけ生成（レンダなし）
  python3 forge_v2.py endless --render     # 延々生成＋Pianoteq レンダ（tmux 用）
  python3 forge_v2.py page --open          # index_v2.html を作って Chrome で開く
"""

import sys
import os
import json
import time
import random
import shutil
import argparse
import subprocess
import html
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import forge  # noqa: E402  V1 の MIDI writer / render_events / Pianoteq / harmony engine
import composer  # noqa: E402  転調パレット（和声セル + 転調技法）の供給元
H = forge.H
PC = H.PC_NAMES

V2 = HERE / "v2"
V2_MIDI = V2 / "midi"
V2_WAV = V2 / "wav"
for d in (V2, V2_MIDI, V2_WAV):
    d.mkdir(exist_ok=True)

SEEN_FILE = V2 / "seen.txt"          # 移調不変シグネチャ（重複排除、再起動越え）
COUNTER_FILE = V2 / "counter.txt"    # seed カウンタ
CATALOG_JSONL = V2 / "catalog.jsonl"
RUN_LOG = V2 / "run.log"

DEFAULT_PRESET = "NY Steinway D Jazz"
SCORE_MIN = 65          # これ未満は捨てる（さらに複雑、を担保）
MIN_FREE_GB = 8         # 空きがこれ未満になったら停止（ディスク保護）


# ─────────────────────────────────────────────
# クオリティ → ピッチクラス集合
# ─────────────────────────────────────────────
def q_pcs(root, quality):
    iv = H._CHORD_QUALITY_INTERVALS.get(quality) or H._CHORD_QUALITY_INTERVALS["maj7"]
    return sorted({(root + i) % 12 for i in iv})


def mk(root, quality, label=None):
    return dict(pcs=q_pcs(root, quality), bass=root % 12, root=root % 12,
                quality=quality, label=label or f"{PC[root % 12]}{quality}")


def mk_pcset(pcs, bass, label, quality="13"):
    return dict(pcs=sorted({p % 12 for p in pcs}), bass=bass % 12, root=bass % 12,
                quality=quality, label=label)


# ─────────────────────────────────────────────
# ジェネレータ群（各 seed で決定論的に1進行を返す）
# ─────────────────────────────────────────────
def _maj7_or_rich(rnd, root, minor):
    if minor:
        return mk(root, rnd.choice(["m7", "m9", "m11"]))
    return mk(root, rnd.choice(["maj7", "maj9", "6/9"]))


def gen_neo_riemannian(seed):
    rnd = random.Random(seed * 2654435761 & 0xFFFFFFFF)
    root = seed % 12
    minor = bool(seed & 1)
    length = rnd.randint(8, 12)
    chords = []
    for _ in range(length):
        chords.append(_maj7_or_rich(rnd, root, minor))
        op = rnd.choice(["P", "L", "R", "L", "R"])  # PLR、L/R 偏重で滑らかに
        if op == "P":
            minor = not minor
        elif op == "R":
            root = (root + (9 if not minor else 3)) % 12
            minor = not minor
        else:  # L
            root = (root + (4 if not minor else 8)) % 12
            minor = not minor
    return dict(technique="neo_riemannian", tonic_pc=seed % 12,
                key_name=PC[seed % 12], bpm=rnd.choice([66, 72, 76, 84]),
                note="ネオ・リーマン PLR 変換の連鎖。隣接和音が共通音を保ったまま"
                     "1〜2 半音だけ動く最大平滑ボイスリーディング。非機能だが必然の流れ。",
                chords=chords)


def gen_octatonic(seed):
    rnd = random.Random(seed * 40503 & 0xFFFFFFFF)
    axis = seed % 3
    roots = [(axis + 3 * k) % 12 for k in range(4)]  # 短3度軸
    rnd.shuffle(roots)
    alts = ["9", "7b9", "7#9", "13", "7b13"]
    chords = []
    for i in range(rnd.randint(8, 10)):
        r = roots[i % 4]
        if rnd.random() < 0.3:
            chords.append(mk((r + 6) % 12, rnd.choice(alts), f"{PC[(r+6)%12]}7(裏)"))
        else:
            chords.append(mk(r, rnd.choice(alts)))
    return dict(technique="octatonic", tonic_pc=axis, key_name=PC[axis],
                bpm=rnd.choice([92, 100, 108]),
                note="オクタトニック（短3度対称）軸上のドミナント／オルタード和音と"
                     "裏コードの循環。どこにも解決しないまま回り続ける緊張の輪。",
                chords=chords)


def gen_hexatonic(seed):
    rnd = random.Random(seed * 22571 & 0xFFFFFFFF)
    base = seed % 4
    aug = [(base + 4 * k) % 12 for k in range(3)]  # 増三和音
    chords = []
    for i in range(rnd.randint(6, 9)):
        r = aug[i % 3]
        if rnd.random() < 0.5:
            chords.append(mk(r, rnd.choice(["maj7", "maj9", "add9"])))
        else:
            chords.append(mk((r + rnd.choice([3, 9])) % 12, rnd.choice(["m9", "m7"])))
    return dict(technique="hexatonic", tonic_pc=base, key_name=PC[base],
                bpm=rnd.choice([60, 66, 70]),
                note="増三和音システム（六音音階）のクロマティックメディアント鎖。"
                     "長3度離れた和音を共通音1で渡る、映画的で神秘的な色変化。",
                chords=chords)


def gen_coltrane_matrix(seed):
    rnd = random.Random(seed * 11939 & 0xFFFFFFFF)
    start = seed % 12
    keys = [(start + 4 * k) % 12 for k in range(3)]
    rnd.shuffle(keys)
    chords = []
    for k in keys:
        chords.append(mk((k + 2) % 12, "m9", f"{PC[(k+2)%12]}m9"))   # ii
        chords.append(mk((k + 7) % 12, rnd.choice(["9", "7b9"]),      # V
                         f"{PC[(k+7)%12]}7"))
        chords.append(mk(k, "maj7", f"{PC[k]}maj7"))                  # I
    return dict(technique="coltrane_matrix", tonic_pc=start, key_name=PC[start],
                bpm=rnd.choice([96, 104, 120]),
                note="長3度で3分割した多重トニックへ、各キーへの II-V-I で次々転調。"
                     "Giant Steps 系の、解決した先がまた次の調になる目眩の連続。",
                chords=chords)


def gen_backcycle(seed):
    rnd = random.Random(seed * 9176 & 0xFFFFFFFF)
    target = seed % 12
    L = rnd.randint(6, 9)
    chords = []
    for i in range(L):
        r = (target + 7 * (L - i)) % 12  # 5度圏を遡る
        chords.append(mk(r, rnd.choice(["9", "7b9", "7#9", "13"])))
    chords.append(mk(target, rnd.choice(["maj9", "6/9"])))  # 解決
    return dict(technique="backcycle", tonic_pc=target, key_name=PC[target],
                bpm=rnd.choice([88, 100, 112]),
                note="拡張ドミナント・バックサイクル。5度圏を遡る V7 of V7 of… の連鎖が"
                     "ずっと「もうすぐ解決する」と言い続け、最後の1和音だけで着地する。",
                chords=chords)


def gen_constant_struct(seed):
    rnd = random.Random(seed * 6133 & 0xFFFFFFFF)
    quality = rnd.choice(["m11", "maj9", "7#9", "m9", "13", "maj13"])
    interval = rnd.choice([1, 2, 3, 4, 5, 6])
    start = seed % 12
    steps = rnd.randint(6, 8)
    direction = rnd.choice([1, -1])
    chords = [mk((start + direction * interval * i) % 12, quality)
              for i in range(steps)]
    names = {1: "半音", 2: "全音", 3: "短3度", 4: "長3度", 5: "完全4度", 6: "三全音"}
    return dict(technique="constant_struct", tonic_pc=start, key_name=PC[start],
                bpm=rnd.choice([72, 80, 88]),
                note=f"コンスタントストラクチャー：{quality} を{names[interval]}間隔で"
                     "そのまま平行移動。和声機能を捨て、響きの色だけを滑らせる現代的手法。",
                chords=chords)


def gen_polychord(seed):
    rnd = random.Random(seed * 49297 & 0xFFFFFFFF)
    bass = seed % 12
    uppers = [2, 8, 10, 5, 6, 4, 1]  # 上部構造トライアドのルート（ベースからの度数）
    rnd.shuffle(uppers)
    moving = rnd.random() < 0.5
    chords = []
    b = bass
    for i in range(rnd.randint(6, 8)):
        u = (b + uppers[i % len(uppers)]) % 12
        triad = [u, (u + 4) % 12, (u + 7) % 12]
        pcs = [b, (b + 7) % 12] + triad
        chords.append(mk_pcset(pcs, b, f"{PC[u]}/{PC[b]}"))
        if moving:
            b = (b + rnd.choice([-2, -1, 2, 5, 7])) % 12
    return dict(technique="polychord", tonic_pc=bass, key_name=PC[bass],
                bpm=rnd.choice([70, 78, 86]),
                note="ベース上の上部構造トライアド（ポリコード）列。下は支え、上は別調の"
                     "明るい三和音。1和音の中に2つの調が同居する立体的な響き。",
                chords=chords)


def gen_negative_harmony(seed):
    rnd = random.Random(seed * 17389 & 0xFFFFFFFF)
    t = seed % 12
    # 機能進行の素（度数, quality）— ランダムに組む
    pool = [
        [(2, "m9"), (7, "9"), (0, "maj7"), (9, "m7")],
        [(0, "maj7"), (5, "maj7"), (2, "m7"), (7, "7b9")],
        [(9, "m7"), (2, "m7"), (7, "9"), (0, "maj9"), (5, "maj7"), (4, "m7")],
    ]
    src = rnd.choice(pool)
    chords = []
    for deg, q in src:
        root = (t + deg) % 12
        pcs0 = q_pcs(root, q)
        # 鏡映: x -> (7 - x + 2t) mod 12
        refl = sorted({(7 - p + 2 * t) % 12 for p in pcs0})
        bass = (7 - root + 2 * t) % 12
        chords.append(mk_pcset(refl, bass, f"–{PC[root]}{q}", quality="m11"))
    return dict(technique="negative_harmony", tonic_pc=t, key_name=PC[t],
                bpm=rnd.choice([72, 80]),
                note="ネガティブ・ハーモニー。トニック–ドミナント軸で各和音を鏡映し、"
                     "長調の進行を裏返した影の進行に。明るさが切なさに反転する。",
                chords=chords)


def gen_side_slip(seed):
    rnd = random.Random(seed * 3457 & 0xFFFFFFFF)
    root = seed % 12
    q = rnd.choice(["m9", "maj9", "m11"])
    slip = rnd.choice([1, -1])
    chords = []
    for i in range(rnd.randint(6, 8)):
        r = root if i % 2 == 0 else (root + slip) % 12
        chords.append(mk(r, q))
    return dict(technique="side_slip", tonic_pc=root, key_name=PC[root],
                bpm=rnd.choice([84, 92, 100]),
                note="サイドスリップ。同じクオリティを半音上下に滑らせて交互に置く。"
                     "アウト感と都会的な不穏。Herbie/Wayne 系の横滑り。",
                chords=chords)


def gen_modulation_journey(seed):
    """4〜7 個のキー領域を実在の転調技法で渡る「転調の旅」。
    パレット（唸る和声セル + 8 転調技法）は composer.py から借りる。
    note 欄に旅程（キー遷移 + 技法名）を載せ、index で転調の道筋を読めるように。"""
    rnd = random.Random(seed * 2246822519 & 0xFFFFFFFF)
    regions = rnd.randint(4, 7)
    pc = seed % 12
    mode = "minor" if (seed >> 4) & 1 else "major"
    start_pc = pc
    chords_abs, journey, keys = [], [], []
    for ri in range(regions):
        cell = rnd.choice(composer.cell_pool(mode))
        chords_abs += composer.place_cell(cell, pc)
        keys.append(composer.key_label(pc, mode))
        journey.append(f"【{composer.key_label(pc, mode)}｜{cell['name']}】")
        if ri < regions - 1:
            move = rnd.choices(composer._MOVES, weights=composer._WEIGHTS)[0](pc, mode, rnd)
            chords_abs += move["connectors"]
            journey.append(f" —{move['name']}→ ")
            pc, mode = move["target_pc"], move["target_mode"]
    dedup = []
    for c in chords_abs:
        if not dedup or dedup[-1] != c:
            dedup.append(c)
    chords = [mk(p, q) for p, q in dedup]
    return dict(technique="modulation_journey", tonic_pc=start_pc,
                key_name=PC[start_pc], bpm=rnd.choice([72, 76, 80, 84, 88]),
                note="転調の旅（" + str(regions) + "領域）：" + "".join(journey),
                chords=chords)


GENERATORS = [
    gen_neo_riemannian, gen_octatonic, gen_hexatonic, gen_coltrane_matrix,
    gen_backcycle, gen_constant_struct, gen_polychord, gen_negative_harmony,
    gen_side_slip, gen_modulation_journey,
]


# ─────────────────────────────────────────────
# ボイシング（PC集合 → 平滑な MIDI 列）＋ ベース
# ─────────────────────────────────────────────
def voice_pcsets(chords, center=61, lo=50, hi=82):
    voicings, roots = [], []
    prev_center = center
    for c in chords:
        notes = []
        for pc in c["pcs"]:
            cands = [pc + 12 * k for k in range(3, 8)]
            cands = [n for n in cands if lo - 8 <= n <= hi + 8]
            if not cands:
                cands = [pc + 60]
            n = min(cands, key=lambda x: abs(x - prev_center))
            notes.append(n)
        notes = sorted(set(notes))
        prev_center = sum(notes) / len(notes)
        voicings.append(notes)
        b = 36 + (c["bass"] % 12)
        roots.append(b)
    return voicings, roots


def signature(prog):
    """移調不変シグネチャ。tonic を 0 に正規化した (bass度数, 和音PC集合) の列。"""
    t = prog["tonic_pc"]
    sig = []
    for c in prog["chords"]:
        bass_deg = (c["bass"] - t) % 12
        pcset = frozenset((p - t) % 12 for p in c["pcs"])
        sig.append((bass_deg, pcset))
    return str(sig)


def complexity(prog):
    pairs = [(c["root"], c["quality"]) for c in prog["chords"]]
    return H.progression_complexity_score(pairs)


# ─────────────────────────────────────────────
# 永続化
# ─────────────────────────────────────────────
def load_seen():
    if SEEN_FILE.exists():
        return set(SEEN_FILE.read_text().splitlines())
    return set()


def v1_signatures():
    """V1 カタログのシグネチャ（被り防止）。"""
    sigs = set()
    for e in forge.CATALOG:
        t = H.parse_key(e["default_key"])[0]
        prog = dict(tonic_pc=t, chords=[
            dict(bass=(t + deg) % 12, pcs=q_pcs((t + deg) % 12, q))
            for deg, q, _ in e["chords"]])
        sigs.add(signature(prog))
    return sigs


def load_counter():
    if COUNTER_FILE.exists():
        try:
            return int(COUNTER_FILE.read_text().strip())
        except ValueError:
            return 0
    return 0


def free_gb(path):
    return shutil.disk_usage(path).free / (1024 ** 3)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(RUN_LOG, "a") as f:
        f.write(line + "\n")


# ─────────────────────────────────────────────
# 1 個生成して書き出し
# ─────────────────────────────────────────────
def forge_one(seed, seen, render, preset, style="rolled"):
    gen = GENERATORS[seed % len(GENERATORS)]
    prog = gen(seed)
    if len(prog["chords"]) < 5:
        return None
    sig = signature(prog)
    if sig in seen:
        return None
    score = complexity(prog)["score"]
    if score < SCORE_MIN:
        return None
    seen.add(sig)
    with open(SEEN_FILE, "a") as f:
        f.write(sig + "\n")

    voicings, roots = voice_pcsets(prog["chords"])
    # 長尺進行（転調の旅など）は周回させず1回。短い技法だけ2周で尺を確保。
    loops = 1 if len(prog["chords"]) >= 16 else 2
    evs = forge.render_events(voicings, roots, style, prog["bpm"],
                              beats_per_chord=2, loops=loops, seed=seed)
    stem = f"{prog['technique']}_{seed:06d}_{prog['key_name'].replace('#','s')}"
    midi_path = V2_MIDI / f"{stem}.mid"
    forge.write_midi(midi_path, evs, prog["bpm"])

    wav_name = None
    if render:
        wav_path = V2_WAV / f"{stem}.wav"
        cmd = [forge.PIANOTEQ, "--headless", "--preset", preset,
               "--midi", str(midi_path), "--wav", str(wav_path),
               "--rate", "44100", "--quiet"]
        try:
            subprocess.run(cmd, check=True, timeout=300,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wav_name = wav_path.name
        except Exception as ex:
            log(f"render fail {stem}: {ex}")

    rec = dict(stem=stem, technique=prog["technique"], key=prog["key_name"],
               bpm=prog["bpm"], score=score, rating=complexity(prog)["rating"],
               labels=" → ".join(c["label"] for c in prog["chords"]),
               note=prog["note"], wav=wav_name)
    with open(CATALOG_JSONL, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ─────────────────────────────────────────────
# index_v2.html
# ─────────────────────────────────────────────
def build_page(limit=400):
    if not CATALOG_JSONL.exists():
        raise SystemExit("[v2] catalog.jsonl が無い。先に生成を。")
    recs = [json.loads(l) for l in CATALOG_JSONL.read_text().splitlines() if l.strip()]
    recs = recs[-limit:][::-1]  # 新しい順
    cards = []
    for r in recs:
        wav = r.get("wav")
        audio = (f'<audio controls preload="none" src="wav/{html.escape(wav)}"></audio>'
                 if wav else '<span class="nowav">WAV 未生成</span>')
        cards.append(f"""
    <article>
      <header><h2>{html.escape(r['technique'])}</h2>
        <span class="tag">{html.escape(r['rating'])} {r['score']}</span>
        <span class="meta">key {html.escape(r['key'])} · {r['bpm']} BPM · #{r['stem'].split('_')[1]}</span>
      </header>
      <p class="prog">{html.escape(r['labels'])}</p>
      <p class="note">{html.escape(r['note'])}</p>
      {audio}
    </article>""")
    total = sum(1 for l in CATALOG_JSONL.read_text().splitlines() if l.strip())
    doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chord Forge V2 — 複雑進行</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ background:#0a0b0f; color:#e7e7ea; font-family:-apple-system,"Hiragino Kaku Gothic ProN",sans-serif; margin:0; padding:32px 18px 80px; }}
  h1 {{ font-size:20px; font-weight:600; letter-spacing:.04em; margin:0 0 4px; }}
  .sub {{ color:#8a8d99; font-size:12px; margin:0 0 28px; }}
  article {{ background:#14161d; border:1px solid #23262f; border-radius:12px; padding:16px 18px; margin:0 auto 14px; max-width:780px; }}
  header {{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }}
  h2 {{ font-size:14px; font-weight:600; margin:0; color:#9fd0ff; }}
  .tag {{ font-size:11px; color:#0a0b0f; background:#ffcf8f; border-radius:5px; padding:1px 7px; }}
  .meta {{ font-size:11px; color:#7c8090; }}
  .prog {{ font-family:"SF Mono",ui-monospace,monospace; font-size:13px; color:#ffd9a0; margin:10px 0 6px; }}
  .note {{ font-size:12px; color:#aeb2bf; line-height:1.6; margin:0 0 12px; }}
  audio {{ width:100%; height:34px; }}
  .nowav {{ font-size:12px; color:#6a6e7a; }}
</style></head><body>
  <h1>Chord Forge V2</h1>
  <p class="sub">アルゴリズム生成 · 複雑度 {SCORE_MIN}+ のみ · 累計 {total} 進行（直近 {len(recs)} 表示）</p>
  {''.join(cards)}
</body></html>"""
    out = HERE / "index_v2.html"
    out.write_text(doc, encoding="utf-8")
    return out


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def cmd_once(args):
    seen = load_seen() | v1_signatures()
    seed = load_counter()
    made = 0
    tries = 0
    while made < args.n and tries < args.n * 40:
        rec = forge_one(seed, seen, args.render, args.preset)
        seed += 1
        tries += 1
        if rec:
            made += 1
            print(f"  ✓ {rec['stem']}  [{rec['rating']} {rec['score']}]  {rec['labels']}")
    COUNTER_FILE.write_text(str(seed))
    build_page()
    print(f"\n{made} 個生成 / index_v2.html 更新")


def cmd_endless(args):
    # 二重起動防止ロック
    lock = V2 / "endless.lock"
    if lock.exists():
        try:
            old = int(lock.read_text().strip())
            os.kill(old, 0)  # 生きてれば例外出ない
            log(f"既に endless が稼働中 (pid={old}) 起動中止")
            return
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # 死んでるロックは奪う
    lock.write_text(str(os.getpid()))

    seen = load_seen() | v1_signatures()
    seed = load_counter()
    made = 0
    log(f"endless 開始 seed={seed} render={args.render} score_min={SCORE_MIN}")
    try:
        while True:
            if free_gb(V2) < MIN_FREE_GB:
                log(f"ディスク空き {free_gb(V2):.1f}GB < {MIN_FREE_GB}GB 停止")
                break
            if args.target and made >= args.target:
                log(f"target {args.target} 到達 停止")
                break
            rec = forge_one(seed, seen, args.render, args.preset)
            seed += 1
            if rec:
                made += 1
                COUNTER_FILE.write_text(str(seed))
                log(f"#{made} {rec['stem']} [{rec['rating']} {rec['score']}]")
                if made % 10 == 0:
                    build_page()
            time.sleep(0.15)
    except KeyboardInterrupt:
        log("中断")
    finally:
        COUNTER_FILE.write_text(str(seed))
        build_page()
        try:
            (V2 / "endless.lock").unlink()
        except FileNotFoundError:
            pass
        log(f"終了 累計生成 {made}（このプロセス）")


def cmd_page(args):
    out = build_page()
    print("index_v2.html:", out)
    if args.open:
        subprocess.run(["open", "-na", "Google Chrome", "--args",
                        "--new-window", str(out)], check=False)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    po = sub.add_parser("once")
    po.add_argument("--n", type=int, default=12)
    po.add_argument("--render", action="store_true")
    po.add_argument("--preset", default=DEFAULT_PRESET)
    po.set_defaults(func=cmd_once)

    pe = sub.add_parser("endless")
    pe.add_argument("--render", action="store_true")
    pe.add_argument("--target", type=int, default=0, help="0=無限")
    pe.add_argument("--preset", default=DEFAULT_PRESET)
    pe.set_defaults(func=cmd_endless)

    pp = sub.add_parser("page")
    pp.add_argument("--open", action="store_true")
    pp.set_defaults(func=cmd_page)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
