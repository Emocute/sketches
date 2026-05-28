"""ops-obsidian-auto-launch — Obsidian URI でファイルを開く.

`reference_obsidian_open` 準拠で `obsidian://open?vault=Downloads&file=<path>` を
合成して `open` 呼び出し。`/` は `%2F` エンコード必須。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-obsidian-auto-launch"

DEFAULT_VAULT = "Downloads"
VAULT_ROOT = Path("~/Downloads").expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops obsidian-auto-launch")
    p.add_argument("md_path")
    p.add_argument("--vault", default=DEFAULT_VAULT)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    md = Path(args.md_path).expanduser().resolve()
    if not md.exists():
        logger.error(TOOL_ID, f"not found: {md}")
        return 2
    try:
        rel = md.relative_to(VAULT_ROOT)
    except ValueError:
        logger.error(TOOL_ID, f"{md} is not under {VAULT_ROOT}")
        return 2
    encoded = urllib.parse.quote(str(rel), safe="")
    uri = f"obsidian://open?vault={args.vault}&file={encoded}"
    print(f"uri: {uri}")
    if not args.apply:
        print("[dry-run]")
        return 0
    subprocess.run(["open", uri])
    logger.done(TOOL_ID, f"opened {rel}")
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
