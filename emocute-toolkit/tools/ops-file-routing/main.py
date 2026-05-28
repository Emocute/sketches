"""ops-file-routing — Downloads 直下に放置されたファイルの PJ 振り分け提案.

`Downloads/` 直下のファイルを拡張子・名前 prefix から推定し、
適切な PJ ディレクトリへ移動する候補を提示する (CLAUDE.md
§ 全PJ共通ルール § ファイル操作 #8 準拠)。
"""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-file-routing"

ROUTING_RULES = [
    ({".wav", ".mp3", ".flac", ".aiff", ".m4a"}, "Studio/inbox"),
    ({".mp4", ".mov", ".webm"}, "Visual/inbox"),
    ({".png", ".jpg", ".jpeg", ".gif", ".webp"}, "Visual/inbox"),
]


def route(path: Path, root: Path) -> Path | None:
    for exts, dest in ROUTING_RULES:
        if path.suffix.lower() in exts:
            return root / dest / path.name
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops file-routing")
    p.add_argument("--downloads-root", default="~/Downloads")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.downloads_root).expanduser().resolve()
    plan = []
    for f in root.iterdir():
        if not f.is_file():
            continue
        if f.name.startswith("."):
            continue
        dest = route(f, root)
        if dest:
            plan.append((f, dest))
    print(f"routing candidates: {len(plan)}")
    for s, d in plan[:30]:
        print(f"  {s.name}  →  {d.relative_to(root)}")
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
    logger.done(TOOL_ID, f"file-routing: {moved}")
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
