"""ops-downloads-weekly-clean — Downloads 直下の週次クリーンアップ.

直下に放置された一時ファイル (Screen Recording, IMG_*, *_trim.mp4 等) を
`_archive/loose_<date>/` に退避。資産削除は禁止 (`feedback_no_delete_no_trash`)。
"""
from __future__ import annotations
import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-downloads-weekly-clean"

PROTECTED = {
    "CLAUDE.md", "MEMORY.md", "README.md", ".git", ".git-hooks", ".gitignore",
    "_archive", ".claude", ".obsidian", ".playwright-mcp", ".vscode",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops downloads-weekly-clean")
    p.add_argument("--downloads-root", default="~/Downloads")
    p.add_argument("--apply", action="store_true")
    return p


def is_loose(path: Path) -> bool:
    # 大型 PJ ディレクトリは触らない (PROTECTED + 普通の直下 dir で大文字始まり)
    if path.is_dir():
        return False
    if path.name in PROTECTED:
        return False
    if path.name.startswith("."):
        return False
    return True


def run(args: argparse.Namespace) -> int:
    root = Path(args.downloads_root).expanduser().resolve()
    target = root / "_archive" / f"loose_{date.today().isoformat()}" / "misc"
    plan = [f for f in root.iterdir() if is_loose(f)]
    print(f"loose root files: {len(plan)}")
    for f in plan[:30]:
        print(f"  • {f.name}")
    if not args.apply:
        print(f"\n[dry-run] would move to: {target}")
        return 0
    target.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in plan:
        d = target / f.name
        if d.exists():
            continue
        shutil.move(str(f), str(d))
        moved += 1
    print(f"✅ archived {moved} files → {target}")
    logger.done(TOOL_ID, f"weekly clean: {moved} archived")
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
