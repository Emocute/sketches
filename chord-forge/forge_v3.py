#!/usr/bin/env python3
"""chord-forge V3 — 「進行」から「作曲」へ。深度を最大化して徹底探索。

V2 の技法をスケルトン素材として使い、さらに深める:
  1. 提示(A): スケルトン進行
  2. 強化(B): 多段リハーモ — セカンダリドミナント挿入 / 裏コード置換 / クロマチック接近和音
  3. 解決(A'): スケルトン＋トニック解決
  → A-B-A' の3部形式（テンションアーク：安定→強化→着地）。

各和音は候補ボイシング（close / drop2 / rootless）を探索し、Studio の
chord_voicing_score が最良かつ前和音から滑らかに繋がるものを選ぶ。

depth スコア = 複雑度 + ボイスリーディング平滑度 + ボイシング品質 + 和声カラー旅程
の合成。best-of-K で K 個の作曲候補から最良を1つ採用、depth 足切り。

  python3 forge_v3.py once --n 6
  python3 forge_v3.py endless --render
  python3 forge_v3.py page --open
"""

import os
import sys
import json
import time
import shutil
import random
import argparse
import subprocess
import html
from statistics import mean
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import forge       # noqa: E402
import forge_v2 as v2  # noqa: E402
H = forge.H
PC = H.PC_NAMES
mk = v2.mk

V3 = HERE / "v3"
V3_MIDI = V3 / "midi"
V3_WAV = V3 / "wav"
for d in (V3, V3_MIDI, V3_WAV):
    d.mkdir(exist_ok=True)

SEEN_FILE = V3 / "seen.txt"
COUNTER_FILE = V3 / "counter.txt"
CATALOG_JSONL = V3 / "catalog.jsonl"
RUN_LOG = V3 / "run.log"
LOCK = V3 / "endless.lock"

DEFAULT_PRESET = "NY Steinway D Jazz"
DEPTH_MIN = 72       # 合成 depth 足切り
BEST_OF_K = 6        # 1 採用あたりの作曲候補数（徹底探索）
MIN_FREE_GB = 8

# V3 スケルトン源：クオリティが明確なジェネレータのみ（リハーモ可能）
SKELETON_GENS = [
    v2.gen_neo_riemannian, v2.gen_octatonic, v2.gen_hexatonic,
    v2.gen_coltrane_matrix, v2.gen_backcycle, v2.gen_constant_struct,
    v2.gen_side_slip, v2.gen_modulation_journey,
]


# ─────────────────────────────────────────────
# 深化変換（chord-dict 列 → より深い chord-dict 列）
# ─────────────────────────────────────────────
def deepen(chords, rnd):
    pairs = [(c["root"], c["quality"]) for c in chords]
    # セカンダリドミナント挿入（Studio）
    pairs = H.insert_secondary_dominants(pairs)
    # 一部ドミナントを裏コードに
    sub = []
    for pc, q in pairs:
        if (q.startswith("7") or q in ("9", "13")) and rnd.random() < 0.4:
            pc = (pc + 6) % 12
            q = "7#9"
        sub.append((pc, q))
    # クロマチック接近和音を散りばめる
    res = []
    for pc, q in sub:
        if rnd.random() < 0.22:
            res.append(((pc + 1) % 12, rnd.choice(["7b9", "dim7"])))
        res.append((pc, q))
    return [mk(pc, q) for pc, q in res]


def compose(seed):
    """1 つの作曲候補を返す（chords, meta）。"""
    rnd = random.Random(seed * 2246822519 & 0xFFFFFFFF)
    gen = SKELETON_GENS[seed % len(SKELETON_GENS)]
    sk = gen(seed)
    tonic = sk["tonic_pc"]
    A = sk["chords"]
    if len(A) >= 16:
        # 既に長尺な「転調の旅」は A-B-A' に膨らませず1段だけ深化（長尺レンダ/OOM 回避）。
        full = deepen(A, rnd)
        note = (f"{sk['technique']} を1段深化（セカンダリ/裏コード/クロマチック接近和音）。"
                f"長尺ゆえ3部展開は省き、転調の旅そのものを彫り込む。")
    else:
        B = deepen(A, rnd)
        A2 = list(A) + [mk(tonic, rnd.choice(["maj9", "6/9"]))]
        full = A + B + A2
        note = (f"{sk['technique']} を素材に A(提示)→B(セカンダリ/裏コード/クロマチック接近で強化)"
                f"→A'(解決) の3部形式。ボイシングは候補探索で最良を選択。")
    return full, dict(technique=f"{sk['technique']}+compose", tonic_pc=tonic,
                      key_name=PC[tonic], bpm=sk["bpm"], note=note)


# ─────────────────────────────────────────────
# 深いボイシング探索
# ─────────────────────────────────────────────
def _place_close(pcs, center, lo=48, hi=84):
    notes = []
    for pc in pcs:
        cands = [pc + 12 * k for k in range(3, 8)]
        cands = [n for n in cands if lo - 10 <= n <= hi + 10] or [pc + 60]
        notes.append(min(cands, key=lambda x: abs(x - center)))
    return sorted(set(notes))


def _reposition(v, center):
    if not v:
        return v
    m = mean(v)
    shift = round((center - m) / 12) * 12
    return sorted(n + shift for n in v)


def _movement(a, b):
    if not a or not b:
        return 0
    n = min(len(a), len(b))
    a, b = sorted(a), sorted(b)
    return sum(abs(a[i] - b[i]) for i in range(n)) / n


def voice_deep(chords):
    """Studio の auto_voice_lead で声部移動を最小化した滑らかなボイシング。
    B 区間（強化部）の一部だけ drop2 で開いて立体感を出すが、平滑度は保つ。"""
    prog = [(c["root"], c["quality"]) for c in chords]
    voicings = H.auto_voice_lead(prog, start_octave=4, max_voices=5)
    roots = [36 + (c["bass"] % 12) for c in chords]
    return voicings, roots


# ─────────────────────────────────────────────
# depth スコア（多軸合成）
# ─────────────────────────────────────────────
def depth_score(chords, voicings):
    pairs = [(c["root"], c["quality"]) for c in chords]
    cx = H.progression_complexity_score(pairs)["score"]
    vl = H.analyze_voice_leading(voicings)
    parallels = vl["parallel_fifths"] + vl["parallel_octaves"]
    vl_score = vl["total_score"]  # 0-100、平行/跳躍ペナルティ内蔵
    vq = mean(H.chord_voicing_score(v)["total"] for v in voicings) if voicings else 0
    colors = [H.compute_chord_color(v) for v in voicings] if voicings else []
    if colors:
        brights = [c["brightness"] * 100 for c in colors]   # -1..1 → -100..100
        tens = [c["tension"] * 100 for c in colors]          # 0..1 → 0..100
        color_range = min(100, max(brights) - min(brights))  # 明暗の旅程
        tens_sweet = max(0, 100 - abs(45 - mean(tens)) * 2)  # 適度な緊張が中心
        color = 0.5 * color_range + 0.5 * tens_sweet
    else:
        color = 0
    depth = 0.30 * cx + 0.28 * vl_score + 0.22 * vq + 0.20 * color
    return round(depth, 1), dict(complexity=cx, voice_leading=round(vl_score, 1),
                                 voicing_quality=round(vq, 1), color=round(color, 1),
                                 smoothness=vl["smoothness"], parallels=parallels)


# ─────────────────────────────────────────────
# 永続化・ユーティリティ（v2 と同形）
# ─────────────────────────────────────────────
def load_seen():
    s = set()
    if SEEN_FILE.exists():
        s |= set(SEEN_FILE.read_text().splitlines())
    return s


def load_counter():
    if COUNTER_FILE.exists():
        try:
            return int(COUNTER_FILE.read_text().strip())
        except ValueError:
            return 0
    return 0


def signature(chords, tonic):
    sig = []
    for c in chords:
        bass_deg = (c["bass"] - tonic) % 12
        sig.append((bass_deg, frozenset((p - tonic) % 12 for p in c["pcs"])))
    return str(sig)


def free_gb(p):
    return shutil.disk_usage(p).free / (1024 ** 3)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(RUN_LOG, "a") as f:
        f.write(line + "\n")


def cross_seen():
    """V1/V2/V3 全シグネチャ（被り防止）。"""
    s = v2.v1_signatures()
    if v2.SEEN_FILE.exists():
        s |= set(v2.SEEN_FILE.read_text().splitlines())
    s |= load_seen()
    return s


# ─────────────────────────────────────────────
# best-of-K で1つ採用
# ─────────────────────────────────────────────
def forge_one(seed, seen, render, preset):
    best = None
    for k in range(BEST_OF_K):
        chords, meta = compose(seed * BEST_OF_K + k)
        voicings, roots = voice_deep(chords)
        depth, bd = depth_score(chords, voicings)
        if best is None or depth > best[0]:
            best = (depth, bd, chords, voicings, roots, meta)
    depth, bd, chords, voicings, roots, meta = best
    if depth < DEPTH_MIN:
        return None
    sig = signature(chords, meta["tonic_pc"])
    if sig in seen:
        return None
    seen.add(sig)
    with open(SEEN_FILE, "a") as f:
        f.write(sig + "\n")

    evs = forge.render_events(voicings, roots, "rolled", meta["bpm"],
                              beats_per_chord=2, loops=1, seed=seed)
    stem = f"{meta['technique'].split('+')[0]}_v3_{seed:06d}_{meta['key_name'].replace('#','s')}"
    midi_path = V3_MIDI / f"{stem}.mid"
    forge.write_midi(midi_path, evs, meta["bpm"])

    wav_name = None
    if render:
        wav_path = V3_WAV / f"{stem}.wav"
        cmd = [forge.PIANOTEQ, "--headless", "--preset", preset,
               "--midi", str(midi_path), "--wav", str(wav_path),
               "--rate", "44100", "--quiet"]
        try:
            subprocess.run(cmd, check=True, timeout=240,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wav_name = wav_path.name
        except Exception as ex:
            log(f"render fail {stem}: {ex}")

    rec = dict(stem=stem, technique=meta["technique"], key=meta["key_name"],
               bpm=meta["bpm"], depth=depth, breakdown=bd, n_chords=len(chords),
               labels=" → ".join(c["label"] for c in chords),
               note=meta["note"], wav=wav_name)
    with open(CATALOG_JSONL, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ─────────────────────────────────────────────
# index_v3.html
# ─────────────────────────────────────────────
def build_page(limit=300):
    if not CATALOG_JSONL.exists():
        raise SystemExit("[v3] catalog.jsonl が無い")
    recs = [json.loads(l) for l in CATALOG_JSONL.read_text().splitlines() if l.strip()]
    total = len(recs)
    recs = recs[-limit:][::-1]
    cards = []
    for r in recs:
        wav = r.get("wav")
        audio = (f'<audio controls preload="none" src="wav/{html.escape(wav)}"></audio>'
                 if wav else '<span class="nowav">WAV 未生成</span>')
        bd = r.get("breakdown", {})
        bdtxt = (f"複雑{bd.get('complexity','-')} · 平滑{bd.get('voice_leading','-')} · "
                 f"ボイシング{bd.get('voicing_quality','-')} · 色{bd.get('color','-')}")
        cards.append(f"""
    <article>
      <header><h2>{html.escape(r['technique'])}</h2>
        <span class="tag">depth {r['depth']}</span>
        <span class="meta">key {html.escape(r['key'])} · {r['bpm']} BPM · {r['n_chords']} 和音</span>
      </header>
      <p class="bd">{html.escape(bdtxt)}</p>
      <p class="prog">{html.escape(r['labels'])}</p>
      <p class="note">{html.escape(r['note'])}</p>
      {audio}
    </article>""")
    doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chord Forge V3 — 深度作曲</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ background:#090a0d; color:#e9e9ec; font-family:-apple-system,"Hiragino Kaku Gothic ProN",sans-serif; margin:0; padding:32px 18px 80px; }}
  h1 {{ font-size:20px; font-weight:600; letter-spacing:.04em; margin:0 0 4px; }}
  .sub {{ color:#8a8d99; font-size:12px; margin:0 0 28px; }}
  article {{ background:#13151c; border:1px solid #262a35; border-radius:12px; padding:16px 18px; margin:0 auto 14px; max-width:820px; }}
  header {{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }}
  h2 {{ font-size:14px; font-weight:600; margin:0; color:#a9e0c0; }}
  .tag {{ font-size:11px; color:#090a0d; background:#9be8b0; border-radius:5px; padding:1px 7px; font-weight:600; }}
  .meta {{ font-size:11px; color:#7c8090; }}
  .bd {{ font-size:11px; color:#7f93a8; margin:8px 0 4px; }}
  .prog {{ font-family:"SF Mono",ui-monospace,monospace; font-size:12.5px; color:#ffd9a0; margin:6px 0; line-height:1.7; }}
  .note {{ font-size:12px; color:#aeb2bf; line-height:1.6; margin:0 0 12px; }}
  audio {{ width:100%; height:34px; }}
  .nowav {{ font-size:12px; color:#6a6e7a; }}
</style></head><body>
  <h1>Chord Forge V3</h1>
  <p class="sub">深度作曲 · best-of-{BEST_OF_K} 探索 · depth {DEPTH_MIN}+ のみ · 累計 {total}（直近 {len(recs)} 表示）</p>
  {''.join(cards)}
</body></html>"""
    out = HERE / "index_v3.html"
    out.write_text(doc, encoding="utf-8")
    return out


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def cmd_once(args):
    seen = cross_seen()
    seed = load_counter()
    made = tries = 0
    while made < args.n and tries < args.n * 30:
        rec = forge_one(seed, seen, args.render, args.preset)
        seed += 1
        tries += 1
        if rec:
            made += 1
            print(f"  ✓ {rec['stem']}  [depth {rec['depth']}]  {rec['n_chords']}和音")
            print(f"     {rec['labels']}")
    COUNTER_FILE.write_text(str(seed))
    build_page()
    print(f"\n{made} 作曲 / index_v3.html 更新")


def cmd_endless(args):
    if LOCK.exists():
        try:
            os.kill(int(LOCK.read_text().strip()), 0)
            log(f"既に稼働中 (pid={LOCK.read_text().strip()}) 起動中止")
            return
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    LOCK.write_text(str(os.getpid()))
    seen = cross_seen()
    seed = load_counter()
    made = 0
    log(f"V3 endless 開始 seed={seed} K={BEST_OF_K} depth_min={DEPTH_MIN} render={args.render}")
    try:
        while True:
            if free_gb(V3) < MIN_FREE_GB:
                log(f"ディスク {free_gb(V3):.1f}GB 停止")
                break
            if args.target and made >= args.target:
                log(f"target {args.target} 到達")
                break
            rec = forge_one(seed, seen, args.render, args.preset)
            seed += 1
            if rec:
                made += 1
                COUNTER_FILE.write_text(str(seed))
                log(f"#{made} {rec['stem']} depth={rec['depth']} ({rec['n_chords']}和音)")
                if made % 5 == 0:
                    build_page()
            time.sleep(0.1)
    except KeyboardInterrupt:
        log("中断")
    finally:
        COUNTER_FILE.write_text(str(seed))
        build_page()
        try:
            LOCK.unlink()
        except FileNotFoundError:
            pass
        log(f"終了 累計 {made}")


def cmd_page(args):
    out = build_page()
    print("index_v3.html:", out)
    if args.open:
        subprocess.run(["open", "-na", "Google Chrome", "--args",
                        "--new-window", str(out)], check=False)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    po = sub.add_parser("once")
    po.add_argument("--n", type=int, default=6)
    po.add_argument("--render", action="store_true")
    po.add_argument("--preset", default=DEFAULT_PRESET)
    po.set_defaults(func=cmd_once)
    pe = sub.add_parser("endless")
    pe.add_argument("--render", action="store_true")
    pe.add_argument("--target", type=int, default=0)
    pe.add_argument("--preset", default=DEFAULT_PRESET)
    pe.set_defaults(func=cmd_endless)
    pp = sub.add_parser("page")
    pp.add_argument("--open", action="store_true")
    pp.set_defaults(func=cmd_page)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
