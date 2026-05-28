"""ops-cache-safe-rm — 再生成可能キャッシュ専用 rm.

CLAUDE.md 1a 例外（`__pycache__/`, `.pytest_cache/`, `.mypy_cache/`,
`.ruff_cache/`, `.DS_Store`, `.nuxt/`, `.next/`）のみ削除対象。
それ以外は絶対に rm しない。サイズ削減を 1 行報告。
"""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-cache-safe-rm"

ALLOWED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".nuxt", ".next"}
ALLOWED_FILES = {".DS_Store"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops cache-safe-rm")
    p.add_argument("root")
    p.add_argument("--apply", action="store_true")
    return p


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    targets = []
    total = 0
    for p in root.rglob("*"):
        if p.is_dir() and p.name in ALLOWED_DIRS:
            sz = dir_size(p)
            targets.append((p, sz))
            total += sz
        elif p.is_file() and p.name in ALLOWED_FILES:
            sz = p.stat().st_size
            targets.append((p, sz))
            total += sz
    print(f"cache targets: {len(targets)}  total: {total/1024/1024:.1f} MB")
    for p, sz in targets[:20]:
        print(f"  {sz/1024:>8.0f} KB  {p.relative_to(root)}")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    removed = 0
    for p, _ in targets:
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            removed += 1
        except OSError:
            pass
    print(f"✅ removed {removed} cache entries, freed {total/1024/1024:.1f} MB")
    logger.done(TOOL_ID, f"cache-rm: {removed} entries / {total/1024/1024:.1f}MB")
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
