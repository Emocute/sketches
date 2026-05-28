"""site-bundle-analyzer — Nuxt ビルド成果物のサイズ解析.

`.output/` 配下の各 chunk サイズを集計、上位を表示。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "site-bundle-analyzer"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site bundle-analyzer")
    p.add_argument("output_dir", help=".output/")
    p.add_argument("--top", type=int, default=20)
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.output_dir).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    files = []
    for f in root.rglob("*"):
        if f.is_file():
            files.append((f, f.stat().st_size))
    files.sort(key=lambda x: -x[1])
    total = sum(s for _, s in files)
    print(f"total files: {len(files)}")
    print(f"total size:  {total/1024/1024:.2f} MB")
    print(f"\ntop {args.top} largest:")
    for f, s in files[:args.top]:
        print(f"  {s/1024:>9.1f} KB  {f.relative_to(root)}")
    logger.done(TOOL_ID, f"bundle {total/1024/1024:.1f}MB, {len(files)} files")
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
