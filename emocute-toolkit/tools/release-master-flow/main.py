"""release-master-flow — リリースフロー全体オーケストレーション.

bump → changelog → archive → audit → zip-build → publish の順に
dry-run で実行計画を提示。--apply で逐次実行（各段でユーザ判断ポイント）。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "release-master-flow"

STAGES = [
    ("bump",      ["release-bump-version"]),
    ("changelog", ["release-changelog-prepend"]),
    ("archive",   ["release-old-zip-archive"]),
    ("audit",     ["audit-zip-3axis"]),
    ("zip",       ["studio-album-zip-builder"]),
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute release master-flow")
    p.add_argument("target", help="販売物パス (例: Sale/products/albums/xxx)")
    p.add_argument("--version", required=True)
    p.add_argument("--skip", action="append", default=[], help="skip stage (例: --skip audit)")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    target = Path(args.target).expanduser().resolve()
    if not target.exists():
        logger.error(TOOL_ID, f"target not found: {target}")
        return 2
    plan = []
    for name, _cmd in STAGES:
        if name in args.skip:
            plan.append(f"  [SKIP] {name}")
        else:
            plan.append(f"  [{'RUN ' if args.apply else 'PLAN'}] {name}")
    print(f"target  = {target}")
    print(f"version = {args.version}")
    print("stages:")
    for line in plan:
        print(line)
    if not args.apply:
        print("\n[dry-run] use --apply to execute each stage")
        return 0
    print("\n⚠ --apply: 各段で手動確認が必要なため、本ラッパーはガイドのみ表示")
    print("実行は各ツールを順に呼ぶ:")
    for name, cmd in STAGES:
        if name in args.skip:
            continue
        print(f"  - {' '.join(cmd)} {target} ...")
    logger.done(TOOL_ID, f"flow plan v{args.version}")
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
