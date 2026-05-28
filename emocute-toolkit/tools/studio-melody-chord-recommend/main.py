"""studio-melody-chord-recommend — メロディから推奨コード進行を提案.

入力 MIDI のメロディラインの音高を分析、各小節での音度を判定、
ダイアトニックの中でメロディと整合するコード候補をスコア順に出力。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-melody-chord-recommend"

try:
    import mido  # type: ignore
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False

# C メジャーキー基準。pitchclass → ダイアトニックコード適合度
DIATONIC = {
    "I":   {"name": "C",  "tones": [0, 4, 7]},
    "ii":  {"name": "Dm", "tones": [2, 5, 9]},
    "iii": {"name": "Em", "tones": [4, 7, 11]},
    "IV":  {"name": "F",  "tones": [5, 9, 0]},
    "V":   {"name": "G",  "tones": [7, 11, 2]},
    "vi":  {"name": "Am", "tones": [9, 0, 4]},
    "vii°":{"name": "Bdim","tones":[11, 2, 5]},
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio melody-chord-recommend")
    p.add_argument("midi")
    p.add_argument("--bars", type=int, default=8, help="小節数で区切る")
    p.add_argument("--json", action="store_true")
    return p


def melody_notes(path: Path) -> list[int]:
    mid = mido.MidiFile(str(path))
    notes = []
    for tr in mid.tracks:
        for msg in tr:
            if msg.type == "note_on" and msg.velocity > 0:
                notes.append(msg.note)
    return notes


def score_chord(melody_pcs: list[int], chord_tones: list[int]) -> int:
    hits = sum(1 for n in melody_pcs if n % 12 in chord_tones)
    return hits


def run(args: argparse.Namespace) -> int:
    if not HAS_MIDO:
        logger.error(TOOL_ID, "mido not installed")
        return 3
    midi = Path(args.midi).expanduser().resolve()
    if not midi.exists():
        logger.error(TOOL_ID, f"not found: {midi}")
        return 2
    notes = melody_notes(midi)
    if not notes:
        logger.error(TOOL_ID, "no notes")
        return 1
    bar_size = max(1, len(notes) // args.bars)
    bars = []
    for i in range(args.bars):
        chunk = notes[i*bar_size:(i+1)*bar_size]
        if not chunk:
            continue
        scores = []
        for sym, info in DIATONIC.items():
            s = score_chord(chunk, info["tones"])
            scores.append((sym, info["name"], s))
        scores.sort(key=lambda x: -x[2])
        bars.append({
            "bar": i+1,
            "candidates": [{"symbol": s[0], "chord": s[1], "score": s[2]} for s in scores[:3]],
        })
    if args.json:
        print(json.dumps(bars, indent=2, ensure_ascii=False))
    else:
        print(f"{midi.name}  ({len(notes)} notes, key=C)")
        for b in bars:
            top = b["candidates"][0]
            alts = ", ".join(f"{c['chord']}({c['score']})" for c in b["candidates"][1:])
            print(f"  bar {b['bar']:2d}: {top['chord']:<5} ({top['score']})  alt: {alts}")
    logger.done(TOOL_ID, f"recommend: {len(bars)} bars")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
