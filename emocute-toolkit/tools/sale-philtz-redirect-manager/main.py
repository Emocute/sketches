"""sale-philtz-redirect-manager — 旧 philtz.com → emocutelab.com リダイレクト管理.

旧 URL → 新 URL のマッピング table を YAML/JSON で管理。
Cloudflare Page Rules / Vercel rewrites の設定原本。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-philtz-redirect-manager"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale philtz-redirect-manager")
    p.add_argument("mapping_json")
    p.add_argument("--format", choices=["vercel", "cloudflare", "list"], default="list")
    return p


def run(args: argparse.Namespace) -> int:
    path = Path(args.mapping_json).expanduser().resolve()
    if not path.exists():
        logger.error(TOOL_ID, f"not found: {path}")
        return 2
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        logger.error(TOOL_ID, f"invalid json: {e}")
        return 2
    if not isinstance(data, dict):
        logger.error(TOOL_ID, "expected dict {from_url: to_url}")
        return 2
    print(f"mappings: {len(data)}")
    if args.format == "list":
        for k, v in data.items():
            print(f"  {k}  →  {v}")
    elif args.format == "vercel":
        redirects = [{"source": k, "destination": v, "permanent": True} for k, v in data.items()]
        print(json.dumps({"redirects": redirects}, indent=2))
    elif args.format == "cloudflare":
        for k, v in data.items():
            print(f"  Rule: {k} → 301 → {v}")
    logger.done(TOOL_ID, f"philtz redirects: {len(data)}")
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
