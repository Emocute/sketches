"""game-numbloom-disc-events — disc サイクルイベント定義の検証.

`project_disc_cycle_correction_2026-03-25` 準拠: disc 0=蜜月→崩壊ループ。
イベント YAML/JSON が「disc 番号と内容の整合性」を保ってるか検査。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-numbloom-disc-events"

EXPECTED_DISCS = list(range(0, 11)) + list(range(9, -1, -1))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game numbloom-disc-events")
    p.add_argument("events_json", help="{disc: N, event: ...} の配列")
    return p


def run(args: argparse.Namespace) -> int:
    p = Path(args.events_json).expanduser().resolve()
    if not p.exists():
        logger.error(TOOL_ID, f"not found: {p}")
        return 2
    try:
        events = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        logger.error(TOOL_ID, f"invalid json: {e}")
        return 2
    if not isinstance(events, list):
        logger.error(TOOL_ID, "expected list")
        return 2
    discs = [e.get("disc") for e in events]
    fail = 0
    print(f"events: {len(events)}")
    print(f"unique discs: {sorted(set(d for d in discs if d is not None))}")
    if 0 not in discs:
        print("  ⚠ disc 0 (蜜月) イベント欠落")
        fail += 1
    if 10 not in discs:
        print("  ⚠ disc 10 (頂点) イベント欠落")
        fail += 1
    crash = [e for e in events if e.get("disc", -1) > 10]
    if crash:
        print(f"  ⚠ disc > 10 のイベント {len(crash)} 件 (cycle 設計違反)")
        fail += 1
    none_disc = [e for e in events if e.get("disc") is None]
    if none_disc:
        print(f"  ⚠ disc 未設定 {len(none_disc)} 件")
        fail += 1
    if fail == 0:
        print("✅ all checks passed")
    logger.done(TOOL_ID, f"disc events: fail={fail}")
    return 0 if fail == 0 else 1


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
