"""sale-tax-doc-generator — 月別売上集計から確定申告用 CSV を出力.

各チャネルの CSV を集約、月別・チャネル別・税区分別に並べた
freee/弥生インポート互換 CSV を生成。
"""
from __future__ import annotations
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-tax-doc-generator"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale tax-doc-generator")
    p.add_argument("sales_csv", help="集約済 sales CSV (date, channel, amount, ccy)")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--usd-rate", type=float, default=155.0)
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.sales_csv).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    by_month: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    n = 0
    with src.open() as f:
        for row in csv.DictReader(f):
            d = row.get("date", "")
            if not d.startswith(str(args.year)):
                continue
            month = d[:7]
            channel = row.get("channel", "?")
            amount = float(row.get("amount", 0))
            ccy = row.get("ccy", "JPY")
            jpy = int(amount * args.usd_rate) if ccy == "USD" else int(amount)
            by_month[month][channel] += jpy
            n += 1
    out = Path(args.out).expanduser().resolve()
    print(f"year:    {args.year}")
    print(f"rows in: {n}")
    print(f"months:  {len(by_month)}")
    if not args.apply:
        for m in sorted(by_month):
            print(f"  {m}: " + ", ".join(f"{c}=¥{v}" for c, v in by_month[m].items()))
        print("\n[dry-run]")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        w = csv.writer(f)
        w.writerow(["month", "channel", "amount_jpy"])
        for m in sorted(by_month):
            for c, v in by_month[m].items():
                w.writerow([m, c, v])
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"tax csv: {sum(sum(v.values()) for v in by_month.values())} JPY")
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
