#!/usr/bin/env python3
"""chord-forge / composer — 転調をふんだんに織り込んだ進行を無限に作る。

カタログ(forge.py)が「名のある定番進行を浴びる蛇口」なら、こちらは
「複数のキーを旅する一回性の進行を延々と鍛造する炉」。

  1曲 = 4〜7個の「キー領域」を旅する。
  各領域に唸る和声セル(ii–V–I 9th / 王道 / 丸サ / andalusian / line cliché /
  harmonic minor cadence …)を置き、領域の継ぎ目を実在の転調技法
  (ピボット ii–V / クロマチックメディアント / 裏コード / Coltrane 長3度 /
   半音上行 / バックドア / 同主調・平行調)で繋ぐ。
  全体を Studio の auto_voice_lead でなめらかに均し、MIDI → Pianoteq WAV。

forge.py の MIDI ライタ / Pianoteq レンダ / 和声エンジン参照を再利用する(複製しない)。
生成物は gen/ に隔離(カタログ midi/ wav/ は触らない)。

  python3 composer.py one  --render            # 1本だけ作って WAV まで
  python3 composer.py many --n 8 --render      # まとめて n 本
  python3 composer.py page --open              # gen.html 再生成して Chrome
"""

import sys
import json
import random
import argparse
import subprocess
import html
from pathlib import Path

import forge  # 兄弟モジュール: MIDI ライタ / render_events / render_wav / 和声エンジン H
H = forge.H

HERE = Path(__file__).resolve().parent
GEN_MIDI = HERE / "gen" / "midi"
GEN_WAV = HERE / "gen" / "wav"
GEN_META = HERE / "gen" / "meta"
GEN_PAGE = HERE / "gen.html"
COUNTER = HERE / "gen" / ".counter"
for d in (GEN_MIDI, GEN_WAV, GEN_META):
    d.mkdir(parents=True, exist_ok=True)

NOTE_NAMES = ["C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B"]
KEY_NAMES = NOTE_NAMES


def note_name(pc):
    return NOTE_NAMES[pc % 12]


def chord_symbol(pc, q):
    qd = "" if q in ("maj", "") else q
    return note_name(pc) + qd


def key_label(pc, mode):
    return f"{note_name(pc)} {'major' if mode == 'major' else 'minor'}"


# ─────────────────────────────────────────────
# 和声セル — (相対度数[半音], quality)。度数はその領域の局所トニックから。
# quality は harmony_utils._CHORD_QUALITY_INTERVALS のキーに限る(起動時検証)。
# ─────────────────────────────────────────────
MAJOR_CELLS = [
    dict(name="ii–V–I (9th)",       degs=[(2, "m9"), (7, "13"), (0, "maj9")]),
    dict(name="王道 4536",          degs=[(5, "maj7"), (7, "9"), (4, "m7"), (9, "m7")]),
    dict(name="丸サ循環",           degs=[(5, "maj9"), (4, "7b9"), (9, "m9"), (0, "9")]),
    dict(name="JTTOU 2536",         degs=[(2, "m9"), (7, "13"), (4, "m7"), (9, "m9")]),
    dict(name="backdoor I",         degs=[(0, "maj9"), (2, "m9"), (10, "13"), (0, "maj9")]),
    dict(name="lydian 上行",        degs=[(0, "maj9"), (2, "7"), (7, "9"), (0, "maj7")]),
    dict(name="借用 iv の翳り",     degs=[(0, "maj7"), (5, "maj7"), (5, "m6"), (0, "maj7")]),
    dict(name="VI–II–V–I",          degs=[(9, "m9"), (2, "m9"), (7, "13"), (0, "maj9")]),
    dict(name="canon 半下行",       degs=[(0, "maj7"), (7, "9"), (9, "m7"), (4, "m7"), (5, "maj7")]),
]

MINOR_CELLS = [
    dict(name="minor ii–V–i",       degs=[(2, "m7b5"), (7, "7b9"), (0, "mMaj7"), (0, "m9")]),
    dict(name="andalusian",         degs=[(0, "m9"), (10, "maj7"), (8, "maj7"), (7, "7b9")]),
    dict(name="line cliché",        degs=[(0, "mMaj7"), (0, "m7"), (0, "m6"), (7, "7b9")]),
    dict(name="harmonic 終止",       degs=[(0, "m9"), (5, "m7"), (7, "7b9"), (0, "mMaj7")]),
    dict(name="phrygian の翳り",     degs=[(0, "m9"), (1, "maj7"), (0, "m9"), (7, "7b9")]),
    dict(name="i–VI–III–VII",       degs=[(0, "m9"), (8, "maj9"), (3, "maj7"), (10, "9")]),
    dict(name="dorian の浮遊",       degs=[(0, "m9"), (5, "9"), (0, "m9"), (10, "maj7")]),
]


def cell_pool(mode):
    return MAJOR_CELLS if mode == "major" else MINOR_CELLS


def place_cell(cell, tonic_pc):
    return [((tonic_pc + d) % 12, q) for d, q in cell["degs"]]


# ─────────────────────────────────────────────
# 転調パレット — (現トニックpc, mode, rnd) → 行き先 + 接続コード(絶対pc) + 技法名
# 接続コードは「次の領域の局所トニックへ向かう橋」。空なら直結(juxtaposition)。
# ─────────────────────────────────────────────
def mod_pivot_iiV(pc, mode, rnd):
    tgt = (pc + rnd.choice([7, 5, 2, 9, 4, 8, 10])) % 12
    tmode = rnd.choices(["major", "minor"], weights=[3, 2])[0]
    if tmode == "minor":
        conn = [((tgt + 2) % 12, "m7b5"), ((tgt + 7) % 12, "7b9")]
    else:
        conn = [((tgt + 2) % 12, "m9"), ((tgt + 7) % 12, "13")]
    return dict(target_pc=tgt, target_mode=tmode, connectors=conn, name="ピボット ii–V")


def mod_chromatic_mediant(pc, mode, rnd):
    tgt = (pc + rnd.choice([3, 4, 8, 9])) % 12
    tmode = rnd.choice(["major", "minor"])
    return dict(target_pc=tgt, target_mode=tmode, connectors=[],
                name="クロマチック・メディアント(直結)")


def mod_tritone(pc, mode, rnd):
    tgt = (pc + rnd.choice([2, 5, 7, 3])) % 12
    tmode = rnd.choice(["major", "minor"])
    conn = [((tgt + 1) % 12, "7#9")]  # ♭II7 → I(裏コード)
    return dict(target_pc=tgt, target_mode=tmode, connectors=conn, name="裏コード(♭II7)経由")


def mod_coltrane(pc, mode, rnd):
    tgt = (pc - 4) % 12  # 長3度下サイクル
    conn = [((tgt + 7) % 12, "7")]
    return dict(target_pc=tgt, target_mode="major", connectors=conn,
                name="長3度サイクル(Coltrane)")


def mod_chromatic_up(pc, mode, rnd):
    tgt = (pc + 1) % 12  # トラックドライバー
    conn = [((tgt + 7) % 12, "7")]
    return dict(target_pc=tgt, target_mode=mode, connectors=conn,
                name="半音上行(トラックドライバー)")


def mod_backdoor(pc, mode, rnd):
    tgt = (pc + rnd.choice([5, 7, 2])) % 12
    conn = [((tgt + 10) % 12, "13")]  # ♭VII7 → I
    return dict(target_pc=tgt, target_mode="major", connectors=conn, name="バックドア(♭VII7)転調")


def mod_parallel(pc, mode, rnd):
    tmode = "minor" if mode == "major" else "major"
    return dict(target_pc=pc, target_mode=tmode, connectors=[], name="同主調チェンジ")


def mod_relative(pc, mode, rnd):
    if mode == "major":
        tgt, tmode = (pc + 9) % 12, "minor"
    else:
        tgt, tmode = (pc + 3) % 12, "major"
    conn = [((tgt + 7) % 12, "7" if tmode == "major" else "7b9")]
    return dict(target_pc=tgt, target_mode=tmode, connectors=conn, name="平行調へ")


MOD_MOVES = [
    (mod_pivot_iiV, 4),
    (mod_chromatic_mediant, 3),
    (mod_tritone, 2),
    (mod_coltrane, 2),
    (mod_chromatic_up, 1),
    (mod_backdoor, 2),
    (mod_parallel, 1),
    (mod_relative, 2),
]
_MOVES = [m for m, _ in MOD_MOVES]
_WEIGHTS = [w for _, w in MOD_MOVES]


# ─────────────────────────────────────────────
# 作曲 — キーの旅を1本組む
# ─────────────────────────────────────────────
def compose(rnd):
    regions = rnd.randint(4, 7)
    pc = rnd.randint(0, 11)
    mode = rnd.choice(["major", "minor"])

    start_pc, start_mode = pc, mode
    chords = []          # 絶対 [(pc, quality)]
    journey = []         # 人間可読の旅程パーツ
    keys_visited = []

    for ri in range(regions):
        cell = rnd.choice(cell_pool(mode))
        chords += place_cell(cell, pc)
        keys_visited.append(key_label(pc, mode))
        journey.append(f"【{key_label(pc, mode)}｜{cell['name']}】")

        if ri < regions - 1:
            move = rnd.choices(_MOVES, weights=_WEIGHTS)[0](pc, mode, rnd)
            if move["connectors"]:
                chords += move["connectors"]
            journey.append(f" —{move['name']}→ ")
            pc, mode = move["target_pc"], move["target_mode"]

    # 連続重複コードを潰す(接続コードが次セル頭と一致した時のスタッタ防止)
    dedup = []
    for c in chords:
        if not dedup or dedup[-1] != c:
            dedup.append(c)
    chords = dedup

    return dict(
        chords=chords,
        symbols=[chord_symbol(p, q) for p, q in chords],
        journey="".join(journey),
        keys=keys_visited,
        regions=regions,
        start_pc=start_pc,
        start_key=keys_visited[0],
    )


# ─────────────────────────────────────────────
# レンダ — 作曲 → MIDI → (Pianoteq) WAV → meta json
# ─────────────────────────────────────────────
def next_seq():
    n = 0
    if COUNTER.exists():
        try:
            n = int(COUNTER.read_text().strip())
        except ValueError:
            n = 0
    n += 1
    COUNTER.write_text(str(n))
    return n


def make_one(rnd, style="rolled", bpm=None, do_render=True, preset=forge.DEFAULT_PRESET):
    piece = compose(rnd)
    bpm = bpm or rnd.choice([72, 76, 80, 84, 88])
    seq = next_seq()
    stem = f"gen_{seq:05d}_{note_name(piece['start_pc']).replace('♭','b')}"

    voicings = H.auto_voice_lead(piece["chords"], start_octave=4, max_voices=5)
    roots = [36 + (p % 12) for p, _ in piece["chords"]]
    evs = forge.render_events(voicings, roots, style, bpm, beats_per_chord=2,
                              loops=1, seed=seq)
    midi_path = GEN_MIDI / f"{stem}.mid"
    forge.write_midi(midi_path, evs, bpm)

    wav_rel = None
    if do_render:
        wav_path, err = _render_wav_gen(midi_path, preset)
        if err:
            print(f"  ! {stem}: {err}")
        elif wav_path:
            wav_rel = wav_path.name

    meta = dict(stem=stem, seq=seq, bpm=bpm, style=style, preset=preset,
                regions=piece["regions"], keys=piece["keys"],
                journey=piece["journey"], symbols=piece["symbols"],
                n_chords=len(piece["chords"]), wav=wav_rel)
    (GEN_META / f"{stem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"  ✓ {stem}  [{piece['regions']}領域 / {len(piece['chords'])}和音]  "
          f"{' · '.join(piece['keys'])}" + (f"  → {wav_rel}" if wav_rel else ""))
    return meta


def _render_wav_gen(midi_path, preset):
    if not Path(forge.PIANOTEQ).exists():
        return None, "Pianoteq 9 が見つからない"
    wav_path = GEN_WAV / (midi_path.stem + ".wav")
    cmd = [forge.PIANOTEQ, "--headless", "--preset", preset,
           "--midi", str(midi_path), "--wav", str(wav_path),
           "--rate", "44100", "--quiet"]
    try:
        subprocess.run(cmd, check=True, timeout=180,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return wav_path, None
    except Exception as ex:
        return None, str(ex)


# ─────────────────────────────────────────────
# gen.html — 旅程付きの聴き比べ
# ─────────────────────────────────────────────
def build_page(preset):
    metas = []
    for j in GEN_META.glob("gen_*.json"):
        try:
            metas.append(json.loads(j.read_text()))
        except Exception:
            pass
    metas.sort(key=lambda m: m.get("seq", 0), reverse=True)

    cards = []
    for m in metas:
        wav = m.get("wav")
        audio = (f'<audio controls preload="none" src="gen/wav/{html.escape(wav)}"></audio>'
                 if wav else '<span class="nowav">WAV 未生成</span>')
        keys = " · ".join(html.escape(k) for k in m.get("keys", []))
        syms = " → ".join(html.escape(s) for s in m.get("symbols", []))
        cards.append(f"""
    <article class="card">
      <div class="head">
        <span class="stem">{html.escape(m['stem'])}</span>
        <span class="meta">{m.get('regions','?')}領域 · {m.get('n_chords','?')}和音 · {m.get('bpm','?')}bpm</span>
      </div>
      <div class="keys">{keys}</div>
      <div class="journey">{html.escape(m.get('journey',''))}</div>
      <div class="syms">{syms}</div>
      {audio}
    </article>""")

    doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>chord-forge / composer — 転調の旅</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0a0a0c; color:#e8e8ea;
         font-family:-apple-system,"Hiragino Kaku Gothic ProN",system-ui,sans-serif; }}
  header {{ padding:28px 24px 14px; border-bottom:1px solid #1c1c22; }}
  h1 {{ margin:0; font-size:19px; letter-spacing:.04em; font-weight:600; }}
  .sub {{ margin:6px 0 0; color:#8a8a93; font-size:12.5px; }}
  main {{ padding:18px 24px 60px; display:grid; gap:14px;
          grid-template-columns:repeat(auto-fill,minmax(420px,1fr)); }}
  .card {{ background:#111116; border:1px solid #1f1f27; border-radius:12px; padding:15px 16px; }}
  .head {{ display:flex; justify-content:space-between; align-items:baseline; gap:10px; }}
  .stem {{ font-size:13px; color:#cfcfd6; font-family:ui-monospace,Menlo,monospace; }}
  .meta {{ font-size:11px; color:#71717a; }}
  .keys {{ margin:9px 0 4px; font-size:13px; color:#b8b3d6; }}
  .journey {{ font-size:11.5px; color:#86868f; line-height:1.65; margin-bottom:7px; }}
  .syms {{ font-size:12px; color:#9aa6b2; line-height:1.7; margin-bottom:11px;
           font-family:ui-monospace,Menlo,monospace; word-break:break-word; }}
  audio {{ width:100%; height:34px; }}
  .nowav {{ font-size:11px; color:#5b5b63; }}
</style></head><body>
<header>
  <h1>chord-forge / composer — 転調の旅</h1>
  <p class="sub">Studio 和声エンジン総動員 · Pianoteq「{html.escape(preset)}」· {len(metas)} pieces · 新しい順</p>
</header>
<main>{''.join(cards)}</main>
</body></html>"""
    GEN_PAGE.write_text(doc)
    return GEN_PAGE


def _open_page(page):
    subprocess.run(["open", "-na", "Google Chrome", "--args",
                    "--new-window", str(page)], check=False)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def cmd_one(args):
    forge.validate_catalog()  # quality 辞書の健全性チェックを共有
    rnd = random.Random()
    make_one(rnd, style=args.style, bpm=args.bpm, do_render=args.render, preset=args.preset)
    page = build_page(args.preset)
    print("gen.html:", page)
    if args.open:
        _open_page(page)


def cmd_many(args):
    forge.validate_catalog()
    rnd = random.Random()
    for _ in range(args.n):
        make_one(rnd, style=args.style, bpm=args.bpm, do_render=args.render, preset=args.preset)
    page = build_page(args.preset)
    print("gen.html:", page)
    if args.open:
        _open_page(page)


def cmd_page(args):
    page = build_page(args.preset)
    print("gen.html:", page)
    if args.open:
        _open_page(page)


def main():
    ap = argparse.ArgumentParser(description="chord-forge / composer — 転調生成エンジン")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--style", choices=["block", "rolled", "arp"], default="rolled")
        p.add_argument("--bpm", type=int, help="省略=70〜88 からランダム")
        p.add_argument("--render", action="store_true", help="Pianoteq で WAV も書く")
        p.add_argument("--open", action="store_true", help="gen.html を Chrome で開く")
        p.add_argument("--preset", default=forge.DEFAULT_PRESET)

    po = sub.add_parser("one"); common(po); po.set_defaults(func=cmd_one)
    pm = sub.add_parser("many"); common(pm)
    pm.add_argument("--n", type=int, default=8)
    pm.set_defaults(func=cmd_many)
    pp = sub.add_parser("page")
    pp.add_argument("--preset", default=forge.DEFAULT_PRESET)
    pp.add_argument("--open", action="store_true")
    pp.set_defaults(func=cmd_page)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
