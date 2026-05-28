"""sale-coupon-bulk-mail — 既存購入者へクーポンメール一括送信プラン.

Resend API + 既存購入者リスト (CSV) からクーポンコード付き送信ジョブを構築。
BOOTH/Gumroad は API クーポン非対応なので Site/Stripe 向け。
"""
from __future__ import annotations
import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-coupon-bulk-mail"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale coupon-bulk-mail")
    p.add_argument("csv_path", help="email,name の CSV")
    p.add_argument("--coupon", required=True, help="Stripe coupon code")
    p.add_argument("--subject", required=True)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    p = Path(args.csv_path).expanduser().resolve()
    if not p.exists():
        logger.error(TOOL_ID, f"not found: {p}")
        return 2
    rows = []
    with p.open() as f:
        for row in csv.DictReader(f):
            if "email" in row:
                rows.append(row)
    print(f"recipients: {len(rows)}")
    print(f"coupon:     {args.coupon}")
    print(f"subject:    {args.subject}")
    for r in rows[:5]:
        print(f"  • {r['email']}  ({r.get('name','-')})")
    if len(rows) > 5:
        print(f"  ... ({len(rows) - 5} more)")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    if not os.environ.get("RESEND_API_KEY"):
        logger.error(TOOL_ID, "RESEND_API_KEY env not set")
        return 2
    print("\n⚠ 実送信は Resend API 経由。本ツールは plan + env 検証のみ")
    print("  実装は infra-resend-bulk-send に分離予定")
    logger.done(TOOL_ID, f"plan: {len(rows)} recipients")
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
