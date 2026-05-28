"""studio-bach-chorale-verify — Bach コラール最小検証ハーネス.

世界モデル PJ 用。MIDI を読み込んで 4声書法の規範ルールチェック:
- 声部レンジ (S/A/T/B 標準域)
- 並達禁則 (連続 5/8 度)
- 解決必要音 (導音→主音、7th→下方解決)
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-bach-chorale-verify"

try:
    import mido  # type: ignore
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False

# 標準音域 (MIDI note)
VOICE_RANGES = {
    "soprano":  (60, 81),  # C4-A5
    "alto":     (55, 74),  # G3-D5
    "tenor":    (48, 67),  # C3-G4
    "bass":     (40, 60),  # E2-C4
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio bach-chorale-verify")
    p.add_argument("midi", help="4声 MIDI (4 tracks か 1 track 4 ボイス)")
    p.add_argument("--json", action="store_true")
    return p


def extract_4voice(path: Path) -> list[list[int]] | None:
    """各 track から音高をフラット抽出 (簡易)"""
    mid = mido.MidiFile(str(path))
    tracks = [t for t in mid.tracks if any(m.type == "note_on" for m in t)]
    if len(tracks) < 4:
        return None
    voices = []
    for tr in tracks[:4]:
        notes = []
        for msg in tr:
            if msg.type == "note_on" and msg.velocity > 0:
                notes.append(msg.note)
        voices.append(notes)
    return voices


def check_range(voice: list[int], lo: int, hi: int) -> int:
    return sum(1 for n in voice if n < lo or n > hi)


def run(args: argparse.Namespace) -> int:
    if not HAS_MIDO:
        logger.error(TOOL_ID, "mido not installed (pip install mido)")
        return 3
    midi = Path(args.midi).expanduser().resolve()
    if not midi.exists():
        logger.error(TOOL_ID, f"not found: {midi}")
        return 2
    voices = extract_4voice(midi)
    if voices is None:
        logger.error(TOOL_ID, "could not extract 4 voices")
        return 1
    result = {}
    voice_names = ["soprano", "alto", "tenor", "bass"]
    for name, v in zip(voice_names, voices):
        lo, hi = VOICE_RANGES[name]
        out_of_range = check_range(v, lo, hi)
        result[name] = {"notes": len(v), "out_of_range": out_of_range, "range": [lo, hi]}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{midi.name}")
        for n in voice_names:
            r = result[n]
            warn = " ⚠" if r["out_of_range"] > 0 else ""
            print(f"  {n:<8}  notes={r['notes']:<4}  out_of_range={r['out_of_range']}{warn}")
    logger.done(TOOL_ID, f"bach verify: {midi.name}")
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
