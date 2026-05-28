"""sale-interview-diff-tracker — 取材原稿バージョン間の diff 追跡.

v1, v2, ..., v_final の md を時系列で並べて、Q ごとに「どこで誰が書き換えたか」
の責任所在 (究 vs Claude vs 編集者) を log.jsonl に記録。
"""
from __future__ import annotations
import argparse
import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-interview-diff-tracker"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale interview-diff-tracker")
    p.add_argument("v_prev")
    p.add_argument("v_next")
    p.add_argument("--label", required=True, help="diff の出所 (例: 究編集 v3→v4)")
    return p


def run(args: argparse.Namespace) -> int:
    a = Path(args.v_prev).expanduser().resolve()
    b = Path(args.v_next).expanduser().resolve()
    if not a.exists() or not b.exists():
        logger.error(TOOL_ID, "input files missing")
        return 2
    al = a.read_text().splitlines()
    bl = b.read_text().splitlines()
    diff = list(difflib.unified_diff(al, bl, fromfile=a.name, tofile=b.name, lineterm=""))
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    print(f"label:   {args.label}")
    print(f"+lines:  {added}")
    print(f"-lines:  {removed}")
    print(f"\n--- diff ---")
    for line in diff[:80]:
        print(line)
    if len(diff) > 80:
        print(f"... ({len(diff) - 80} more)")
    logger.done(TOOL_ID, f"diff +{added}/-{removed} [{args.label}]")
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
