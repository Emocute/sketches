"""studio-midi-chord-extract — MIDI から chord 進行を抽出.

同時鳴った note を集めて chord symbol 推定（基本 12 triad + 7th）。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-midi-chord-extract"

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# pitch class set → chord 記号
CHORD_MAP: dict[frozenset, str] = {
    frozenset({0, 4, 7}): "",
    frozenset({0, 3, 7}): "m",
    frozenset({0, 4, 7, 10}): "7",
    frozenset({0, 3, 7, 10}): "m7",
    frozenset({0, 4, 7, 11}): "M7",
    frozenset({0, 3, 6}): "dim",
    frozenset({0, 4, 8}): "aug",
    frozenset({0, 3, 6, 10}): "m7♭5",
    frozenset({0, 3, 6, 9}): "dim7",
    frozenset({0, 5, 7}): "sus4",
    frozenset({0, 2, 7}): "sus2",
}


def detect_chord(pcs: set[int]) -> str | None:
    """各 pitch を root と仮定して chord 記号探索"""
    for root in pcs:
        normalized = frozenset((p - root) % 12 for p in pcs)
        if normalized in CHORD_MAP:
            return NOTE_NAMES[root] + CHORD_MAP[normalized]
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio midi-chord-extract")
    p.add_argument("input", help="MIDI file")
    p.add_argument("--quantize", type=float, default=0.5,
                   help="同時打鍵とみなす秒数 (default 0.5)")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    try:
        import mido
    except ImportError:
        logger.error(TOOL_ID, "pip install mido")
        return 3
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    mid = mido.MidiFile(str(inp))
    notes_on: dict[int, float] = {}
    events: list[tuple[float, int, str]] = []  # (time, note, on/off)
    t = 0
    for msg in mid:
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            events.append((t, msg.note, "on"))
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            events.append((t, msg.note, "off"))

    # window 内に同時に鳴っている notes を pitch class セット化
    chords: list[dict] = []
    active: dict[int, float] = {}
    cur_window_start = None
    for time, note, kind in events:
        if kind == "on":
            active[note] = time
            if cur_window_start is None:
                cur_window_start = time
        else:
            active.pop(note, None)
        # window 越えた時点で確定
        if cur_window_start is not None and time - cur_window_start > args.quantize:
            if active:
                pcs = {n % 12 for n in active}
                sym = detect_chord(pcs)
                chords.append({"time": round(cur_window_start, 3),
                               "notes": sorted(active.keys()),
                               "chord": sym or f"?{sorted(pcs)}"})
                cur_window_start = time
            else:
                cur_window_start = None

    if args.json:
        print(json.dumps(chords, indent=2))
    else:
        print(f"detected {len(chords)} chord events")
        for c in chords[:50]:
            print(f"  {c['time']:>7.2f}s  {c['chord']}")
        if len(chords) > 50:
            print(f"  ... ({len(chords) - 50} more)")
    logger.done(TOOL_ID, f"{len(chords)} chords from {inp.name}")
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
