"""studio-melody-contour — メロディ輪郭 (上昇/下降/反復) のラベル列を抽出.

Parsons code 風 (U/D/R) の表現でメロディの形状を表す。
類似メロディ検索や Numbloom/HarmonyScope の特徴量入力に。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-melody-contour"

try:
    import mido  # type: ignore
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio melody-contour")
    p.add_argument("midi")
    p.add_argument("--json", action="store_true")
    return p


def parsons(notes: list[int]) -> str:
    if not notes:
        return ""
    out = "*"  # 開始符
    for prev, cur in zip(notes, notes[1:]):
        if cur > prev:
            out += "U"
        elif cur < prev:
            out += "D"
        else:
            out += "R"
    return out


def run(args: argparse.Namespace) -> int:
    if not HAS_MIDO:
        logger.error(TOOL_ID, "mido not installed")
        return 3
    midi = Path(args.midi).expanduser().resolve()
    if not midi.exists():
        logger.error(TOOL_ID, f"not found: {midi}")
        return 2
    mid = mido.MidiFile(str(midi))
    notes = []
    for tr in mid.tracks:
        for msg in tr:
            if msg.type == "note_on" and msg.velocity > 0:
                notes.append(msg.note)
    if not notes:
        logger.error(TOOL_ID, "no notes")
        return 1
    p = parsons(notes)
    counts = {"U": p.count("U"), "D": p.count("D"), "R": p.count("R")}
    if args.json:
        print(json.dumps({"parsons": p, "counts": counts, "n_notes": len(notes)}, indent=2))
    else:
        print(f"notes: {len(notes)}")
        print(f"parsons: {p[:120]}{'...' if len(p) > 120 else ''}")
        print(f"  U={counts['U']}  D={counts['D']}  R={counts['R']}")
    logger.done(TOOL_ID, f"contour {len(p)}")
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
