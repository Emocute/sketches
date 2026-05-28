"""site-vercel-env-add — vercel env add のラッパー.

`reference_vercel_cli_preview_env` 準拠で `vercel env add NAME preview "" --value`
を構築して dry-run。`--apply` で実行。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "site-vercel-env-add"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site vercel-env-add")
    p.add_argument("name")
    p.add_argument("--value", required=True)
    p.add_argument("--env", choices=["preview", "production", "development"], default="preview")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    cmd = ["vercel", "env", "add", args.name, args.env, "", "--value", args.value, "--yes"]
    print("→", " ".join(cmd[:-2]), "[VALUE_REDACTED]", cmd[-1])
    if not args.apply:
        print("\n[dry-run]")
        return 0
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"vercel env add failed: {r.stderr[-200:]}")
        return 3
    print(r.stdout.strip())
    logger.done(TOOL_ID, f"env add {args.name} ({args.env})")
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
