"""ops-obsidian-elasticsearch — Obsidian vault 内 全文検索 (whoosh ローカル).

Downloads vault (135K files、`reference_obsidian_downloads_vault`) は
正規 ES デプロイには大きすぎる。本ツールはローカル grep -r を高速化する
薄ラッパで、`userIgnoreFilters` 互換の除外パスを尊重する。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-obsidian-elasticsearch"

DEFAULT_EXCLUDES = ["_archive", "node_modules", ".git", ".obsidian", "target", ".next", ".nuxt"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops obsidian-elasticsearch")
    p.add_argument("query")
    p.add_argument("--vault-root", default="~/Downloads")
    p.add_argument("--ext", default="md")
    p.add_argument("--limit", type=int, default=30)
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.vault_root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    cmd = ["rg", "-n", "-i", "--glob", f"*.{args.ext}"]
    for x in DEFAULT_EXCLUDES:
        cmd += ["--glob", f"!**/{x}/**"]
    cmd += [args.query, str(root)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        logger.error(TOOL_ID, "ripgrep (rg) not installed")
        return 3
    lines = r.stdout.splitlines()
    print(f"matches: {len(lines)}")
    for line in lines[:args.limit]:
        print(f"  {line}")
    logger.done(TOOL_ID, f"query='{args.query}' hits={len(lines)}")
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
