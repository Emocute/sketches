"""mem-backlink-index — memory ファイル間の参照関係を逆引きインデックス生成.

各 .md ファイル内の `[*](other.md)` リンクを収集し、被参照リスト出力。
孤立ファイル・ハブファイル把握用。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "mem-backlink-index"
MEMORY_DIR = Path.home() / ".claude/projects/-Users-emocute-Downloads/memory"
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+\.md)\)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute mem backlink-index")
    p.add_argument("--memory-dir", default=str(MEMORY_DIR))
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    d = Path(args.memory_dir).expanduser().resolve()
    files = list(d.glob("*.md"))
    backlinks: dict[str, list[str]] = defaultdict(list)
    for f in files:
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for m in LINK_RE.finditer(text):
            target = m.group(1).split("#")[0].split("/")[-1]
            backlinks[target].append(f.name)

    # 孤立: backlink 0 (MEMORY.md と _archive は除く)
    orphans = []
    hubs = []
    for f in files:
        if f.name == "MEMORY.md":
            continue
        n = len(backlinks.get(f.name, []))
        if n == 0:
            orphans.append(f.name)
        elif n >= 5:
            hubs.append((f.name, n))

    if args.json:
        print(json.dumps({
            "backlinks": dict(backlinks),
            "orphans": orphans,
            "hubs": dict(hubs),
        }, indent=2, ensure_ascii=False))
    else:
        print(f"backlink index for {len(files)} files")
        print(f"\n=== HUBS (≥5 incoming) ===")
        for name, n in sorted(hubs, key=lambda x: -x[1])[:20]:
            print(f"  {n:>3}  {name}")
        print(f"\n=== ORPHANS (no incoming) ===")
        for o in orphans[:30]:
            print(f"  {o}")
        if len(orphans) > 30:
            print(f"  ... ({len(orphans) - 30} more)")
        print(f"\ntotal orphans: {len(orphans)}")

    logger.done(TOOL_ID, f"hubs={len(hubs)} orphans={len(orphans)}")
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
