"""ops-task-monthly-archive — TODO.md 完了タスクの月次アーカイブ.

`<PJ>/TODO.md` から `- [x]` で始まる完了タスクを `<PJ>/TODO_archive/<YYYY-MM>.md` に
移動。アクティブセクションを身軽に保つ。
"""
from __future__ import annotations
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-task-monthly-archive"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops task-monthly-archive")
    p.add_argument("todo_md")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.todo_md).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    lines = src.read_text(errors="ignore").splitlines()
    done = [l for l in lines if l.lstrip().startswith("- [x]")]
    active = [l for l in lines if not l.lstrip().startswith("- [x]")]
    print(f"done tasks: {len(done)}")
    print(f"active tasks: {sum(1 for l in active if l.lstrip().startswith('- [ ]'))}")
    if not done:
        print("(nothing to archive)")
        return 0
    if not args.apply:
        print("\n[dry-run]")
        return 0
    archive_dir = src.parent / "TODO_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    month_file = archive_dir / f"{date.today().strftime('%Y-%m')}.md"
    header = f"# Archived from {src.name} on {date.today().isoformat()}\n\n"
    if month_file.exists():
        month_file.write_text(month_file.read_text() + "\n" + header + "\n".join(done))
    else:
        month_file.write_text(header + "\n".join(done))
    src.write_text("\n".join(active))
    print(f"✅ archived {len(done)} tasks → {month_file}")
    logger.done(TOOL_ID, f"task archive: {len(done)}")
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
