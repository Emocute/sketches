"""ops-archive-auto-classify — `_archive/loose_<date>/` の自動振り分け.

ファイル種別 (画像/動画/音/MD/コード/その他) で `misc/` `screenshots/` 配下に
振り分け。`feedback_no_delete_no_trash` 準拠で削除は一切しない、移動のみ。
"""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-archive-auto-classify"

CATEGORIES = {
    "screenshots": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic"},
    "videos": {".mp4", ".mov", ".webm", ".mkv"},
    "audio": {".mp3", ".wav", ".aiff", ".flac", ".m4a", ".ogg"},
    "docs": {".md", ".txt", ".pdf"},
    "code": {".py", ".js", ".ts", ".sh", ".rs", ".go", ".html", ".css"},
    "misc": set(),
}


def classify(ext: str) -> str:
    e = ext.lower()
    for cat, exts in CATEGORIES.items():
        if e in exts:
            return cat
    return "misc"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops archive-auto-classify")
    p.add_argument("loose_dir", help="_archive/loose_<date>/")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.loose_dir).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    plan = []
    for f in src.iterdir():
        if not f.is_file():
            continue
        cat = classify(f.suffix)
        dest = src / cat / f.name
        plan.append((f, dest))
    print(f"files to classify: {len(plan)}")
    by_cat: dict[str, int] = {}
    for _, d in plan:
        by_cat[d.parent.name] = by_cat.get(d.parent.name, 0) + 1
    for c, n in by_cat.items():
        print(f"  {c}: {n}")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    moved = 0
    for s, d in plan:
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.exists():
            continue
        shutil.move(str(s), str(d))
        moved += 1
    print(f"✅ moved {moved}")
    logger.done(TOOL_ID, f"archive classified: {moved}")
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
