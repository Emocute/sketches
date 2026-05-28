"""ops-memory-backlink-index — memory 内 backlink index 生成.

`~/.claude/projects/-Users-emocute-Downloads/memory/*.md` を全件読んで
ファイル名同士の cross-reference を列挙、孤立 (in-link 0) の memory を warn。
"""
from __future__ import annotations
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-memory-backlink-index"

DEFAULT_ROOT = "~/.claude/projects/-Users-emocute-Downloads/memory"
LINK_RE = re.compile(r"([a-z][a-z0-9_]+\.md)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops memory-backlink-index")
    p.add_argument("--memory-root", default=DEFAULT_ROOT)
    p.add_argument("--show-orphans", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.memory_root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    inbound = defaultdict(set)
    files = list(root.glob("*.md"))
    names = {f.name for f in files}
    for f in files:
        text = f.read_text(errors="ignore")
        for m in LINK_RE.findall(text):
            if m in names and m != f.name:
                inbound[m].add(f.name)
    orphans = [n for n in names if not inbound.get(n)]
    print(f"memory files: {len(files)}")
    print(f"with backlinks: {len(files) - len(orphans)}")
    print(f"orphans (no in-link): {len(orphans)}")
    if args.show_orphans:
        for o in sorted(orphans)[:40]:
            print(f"  ⚠ {o}")
    logger.done(TOOL_ID, f"backlink index: orphans={len(orphans)}")
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
