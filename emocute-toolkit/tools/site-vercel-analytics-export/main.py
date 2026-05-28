"""site-vercel-analytics-export — Vercel Analytics の生データ取得.

`VERCEL_TOKEN` を使って `/v1/insights/...` を叩く。Hobby プランでは
細粒データ取れないので、Pro 以上前提。本ツールは plan + 環境変数チェック。
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "site-vercel-analytics-export"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site vercel-analytics-export")
    p.add_argument("--project-id", required=True)
    p.add_argument("--from-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--to-date",   required=True)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    if not os.environ.get("VERCEL_TOKEN"):
        logger.error(TOOL_ID, "VERCEL_TOKEN env not set")
        return 2
    print(f"project:  {args.project_id}")
    print(f"period:   {args.from_date} → {args.to_date}")
    print(f"endpoint: https://api.vercel.com/v1/insights/{args.project_id}/...")
    if not args.apply:
        print("\n[dry-run] (Hobby plan では制限大、Pro 必須)")
        return 0
    print("\n⚠ Hobby プランでは詳細データ取れない")
    print("実装: httpx で GET, Authorization: Bearer $VERCEL_TOKEN")
    logger.done(TOOL_ID, f"plan {args.from_date}~{args.to_date}")
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
