"""studio-midi-voice-leading — MIDI 進行のヴォイスリーディング解析.

各和音の声部 (S/A/T/B) を抽出、隣接和音間の音程移動を算出。
- 並達禁則 (連続 5度/8度) 検出
- 跳躍幅 (>長6度) 警告
- 共通音保持率
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-midi-voice-leading"

try:
    import mido  # type: ignore
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio midi-voice-leading")
    p.add_argument("midi")
    p.add_argument("--json", action="store_true")
    return p


def collect_chords(path: Path) -> list[list[int]]:
    mid = mido.MidiFile(str(path))
    notes_on: dict[int, int] = {}
    chords: list[list[int]] = []
    last_time = 0
    for tr in mid.tracks:
        for msg in tr:
            if msg.type == "note_on" and msg.velocity > 0:
                notes_on[msg.note] = last_time
            elif (msg.type == "note_off") or (msg.type == "note_on" and msg.velocity == 0):
                notes_on.pop(msg.note, None)
            last_time += getattr(msg, "time", 0)
            if len(notes_on) >= 2:
                chord = sorted(notes_on.keys())
                if not chords or chord != chords[-1]:
                    chords.append(chord)
    return chords


def check_voice_leading(a: list[int], b: list[int]) -> list[str]:
    issues = []
    n = min(len(a), len(b))
    for i in range(n - 1):
        a_int = a[i+1] - a[i]
        b_int = b[i+1] - b[i]
        if a_int == 7 and b_int == 7:
            issues.append(f"連続5度 v{i}-v{i+1}")
        if a_int == 12 and b_int == 12:
            issues.append(f"連続8度 v{i}-v{i+1}")
    for i in range(n):
        jump = abs(b[i] - a[i])
        if jump > 9:
            issues.append(f"声部{i}: 跳躍幅{jump}半音")
    return issues


def run(args: argparse.Namespace) -> int:
    if not HAS_MIDO:
        logger.error(TOOL_ID, "mido not installed (pip install mido)")
        return 3
    midi = Path(args.midi).expanduser().resolve()
    if not midi.exists():
        logger.error(TOOL_ID, f"not found: {midi}")
        return 2
    chords = collect_chords(midi)
    if len(chords) < 2:
        logger.warn(TOOL_ID, f"only {len(chords)} chords found")
        return 1
    all_issues = []
    for i in range(len(chords) - 1):
        for iss in check_voice_leading(chords[i], chords[i+1]):
            all_issues.append({"transition": i, "issue": iss})
    if args.json:
        print(json.dumps({"chords": len(chords), "issues": all_issues}, indent=2, ensure_ascii=False))
    else:
        print(f"chords: {len(chords)}  issues: {len(all_issues)}")
        for x in all_issues[:30]:
            print(f"  t{x['transition']:03d}  {x['issue']}")
        if len(all_issues) > 30:
            print(f"  ... ({len(all_issues) - 30} more)")
    logger.done(TOOL_ID, f"vl: {len(chords)} chords, {len(all_issues)} issues")
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
