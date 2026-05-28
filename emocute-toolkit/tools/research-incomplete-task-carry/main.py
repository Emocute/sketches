"""research-incomplete-task-carry — 未完タスクの繰越カウント.

各 PJ の TODO.md にある `- [ ]` 未完タスクの数を集計、長期未完
(最終編集 14 日以上前) を warn。
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "research-incomplete-task-carry"

WARN_DAYS = 14


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute research incomplete-task-carry")
    p.add_argument("--downloads-root", default="~/Downloads")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.downloads_root).expanduser().resolve()
    todos = list(root.glob("*/TODO.md"))
    total_open = 0
    stale = 0
    print(f"TODO.md files: {len(todos)}")
    for t in todos:
        text = t.read_text(errors="ignore")
        open_count = sum(1 for l in text.splitlines() if l.lstrip().startswith("- [ ]"))
        total_open += open_count
        mtime = datetime.fromtimestamp(t.stat().st_mtime, tz=timezone.utc)
        days = (datetime.now(timezone.utc) - mtime).days
        marker = " ⚠ stale" if days >= WARN_DAYS and open_count > 0 else ""
        if days >= WARN_DAYS and open_count > 0:
            stale += 1
        print(f"  {open_count:>4} open  {days:>4}d  {t.parent.name}{marker}")
    print(f"\ntotal open tasks: {total_open}")
    print(f"stale TODOs (>{WARN_DAYS}d): {stale}")
    logger.done(TOOL_ID, f"open={total_open} stale={stale}")
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
