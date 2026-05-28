"""sale-landr-contract-reminder — LANDR Studio Pro 月契約の終了リマインダ.

契約開始日から 30 日前後で notification 発火する LaunchAgent 用設定を生成。
`landr_batch_remaster_plan` 準拠で 1ヶ月契約 → bulk リマスタリング戦略。
"""
from __future__ import annotations
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-landr-contract-reminder"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale landr-contract-reminder")
    p.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--warn-before", type=int, default=3)
    return p


def run(args: argparse.Namespace) -> int:
    try:
        start = dt.date.fromisoformat(args.start_date)
    except ValueError:
        logger.error(TOOL_ID, f"bad date: {args.start_date}")
        return 2
    end = start + dt.timedelta(days=30)
    warn_at = end - dt.timedelta(days=args.warn_before)
    today = dt.date.today()
    days_to_warn = (warn_at - today).days
    days_to_end = (end - today).days
    print(f"start:     {start}")
    print(f"end (30d): {end}")
    print(f"warn at:   {warn_at} ({args.warn_before} days before end)")
    print(f"today:     {today}")
    print(f"  → days until warn: {days_to_warn}")
    print(f"  → days until end:  {days_to_end}")
    if days_to_end <= 0:
        print("\n⚠ 契約期間終了済")
    elif days_to_warn <= 0:
        print("\n⚠ 警告期間内: 解約手続き要")
    logger.done(TOOL_ID, f"end {end} (in {days_to_end}d)")
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
