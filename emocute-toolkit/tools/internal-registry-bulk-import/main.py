"""internal-registry-bulk-import — registry/_status.yaml バルクインポート.

外部 yaml/csv からツール定義を一括取り込み (phase/category/priority/status)。
重複は skip、新規のみ追記。
"""
from __future__ import annotations
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "internal-registry-bulk-import"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute internal registry-bulk-import")
    p.add_argument("csv_path")
    p.add_argument("--target", default="registry/_status.yaml")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.csv_path).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    target = Path(args.target).expanduser().resolve()
    existing = target.read_text() if target.exists() else ""
    rows = list(csv.DictReader(src.open()))
    new_lines = []
    for r in rows:
        tid = r.get("id")
        if not tid or tid in existing:
            continue
        line = f"  {tid}: {{ phase: {r.get('phase','5')}, category: {r.get('category','misc')}, priority: {r.get('priority','low')}, status: planned }}"
        new_lines.append(line)
    print(f"csv rows: {len(rows)}  new: {len(new_lines)}")
    if not args.apply:
        for line in new_lines[:10]:
            print(f"  + {line.strip()}")
        print("\n[dry-run]")
        return 0
    with target.open("a") as f:
        f.write("\n" + "\n".join(new_lines) + "\n")
    print(f"✅ appended {len(new_lines)} rows")
    logger.done(TOOL_ID, f"bulk import: {len(new_lines)}")
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
