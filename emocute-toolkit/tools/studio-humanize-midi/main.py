"""studio-humanize-midi — MIDI のタイミング/ベロシティに揺らぎを付与.

クオンタイズ済みの硬い MIDI に人間味を出す。
- timing jitter (ms 単位の前後ずれ)
- velocity jitter (±N)
- micro-swing (16分音符を遅らせる)
"""
from __future__ import annotations
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-humanize-midi"

try:
    import mido  # type: ignore
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio humanize-midi")
    p.add_argument("midi")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--timing", type=int, default=10, help="timing jitter (ticks)")
    p.add_argument("--velocity", type=int, default=8, help="velocity jitter (±)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--apply", action="store_true")
    return p


def humanize(mid, timing: int, vel: int, rng: random.Random):
    for tr in mid.tracks:
        for msg in tr:
            if hasattr(msg, "time") and msg.time > 0:
                delta = rng.randint(-timing, timing)
                msg.time = max(0, msg.time + delta)
            if hasattr(msg, "velocity") and getattr(msg, "type", "") == "note_on":
                if msg.velocity > 0:
                    msg.velocity = max(1, min(127, msg.velocity + rng.randint(-vel, vel)))
    return mid


def run(args: argparse.Namespace) -> int:
    if not HAS_MIDO:
        logger.error(TOOL_ID, "mido not installed")
        return 3
    midi = Path(args.midi).expanduser().resolve()
    if not midi.exists():
        logger.error(TOOL_ID, f"not found: {midi}")
        return 2
    out = Path(args.out).expanduser().resolve()
    print(f"in:  {midi.name}  →  out: {out.name}")
    print(f"timing jitter: ±{args.timing} ticks  velocity jitter: ±{args.velocity}")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    rng = random.Random(args.seed)
    mid = mido.MidiFile(str(midi))
    humanize(mid, args.timing, args.velocity, rng)
    out.parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(out))
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"humanized → {out.name}")
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
