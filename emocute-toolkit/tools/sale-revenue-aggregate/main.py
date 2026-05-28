"""sale-revenue-aggregate — Gumroad/BOOTH/Stripe CSV を統合集計.

各チャネルの売上 CSV をディレクトリに置き、月次/商品別合算。
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-revenue-aggregate"

# 各チャネルの列マッピング推測。CSV 形式違いに対応。
CHANNEL_HINTS = {
    "gumroad": {"amount": ["Sale price", "Net amount", "Amount"],
                "date": ["Created at", "Date", "Sale time"],
                "product": ["Product name", "Item", "Name"],
                "currency": ["Currency"]},
    "booth": {"amount": ["金額", "売上", "amount"],
              "date": ["注文日", "日付", "date"],
              "product": ["商品名", "title"]},
    "stripe": {"amount": ["Amount", "amount"],
               "date": ["Created (UTC)", "created"],
               "product": ["Description", "description"]},
}

# Currency normalization (very rough)
RATE_TO_JPY = {"USD": 155.0, "EUR": 165.0, "JPY": 1.0}


def detect_channel(path: Path) -> str:
    name = path.name.lower()
    for ch in CHANNEL_HINTS:
        if ch in name:
            return ch
    return "unknown"


def find_col(headers: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        for h in headers:
            if h.strip().lower() == c.lower():
                return h
    return None


def parse_csv(path: Path) -> list[dict]:
    channel = detect_channel(path)
    hints = CHANNEL_HINTS.get(channel, CHANNEL_HINTS["gumroad"])
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        col_amount = find_col(headers, hints["amount"])
        col_date = find_col(headers, hints["date"])
        col_product = find_col(headers, hints["product"])
        col_currency = find_col(headers, hints.get("currency", []))
        for r in reader:
            try:
                amt_str = (r.get(col_amount, "0") or "0").replace("$", "").replace("¥", "").replace(",", "").strip()
                amt = float(amt_str) if amt_str else 0.0
            except ValueError:
                amt = 0.0
            cur = (r.get(col_currency, "JPY") if col_currency else
                   ("JPY" if channel == "booth" else "USD"))
            cur = cur.strip().upper() if cur else "JPY"
            amt_jpy = amt * RATE_TO_JPY.get(cur, 1.0)
            date = (r.get(col_date, "") or "")[:10]
            product = (r.get(col_product, "") or "(unknown)").strip()
            rows.append({"channel": channel, "date": date, "month": date[:7],
                         "product": product, "amount_jpy": amt_jpy,
                         "amount_orig": amt, "currency": cur})
    return rows


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale revenue-aggregate")
    p.add_argument("dir", help="CSV が並ぶディレクトリ")
    p.add_argument("--by", choices=["month", "product", "channel"], default="month")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    d = Path(args.dir).expanduser().resolve()
    if not d.is_dir():
        logger.error(TOOL_ID, f"not dir: {d}")
        return 2
    files = list(d.glob("*.csv"))
    if not files:
        logger.warn(TOOL_ID, "no csv found")
        return 1
    all_rows = []
    for f in files:
        all_rows += parse_csv(f)
    print(f"parsed {len(files)} files, {len(all_rows)} rows")
    buckets: dict[str, float] = defaultdict(float)
    for r in all_rows:
        buckets[r[args.by]] += r["amount_jpy"]

    if args.json:
        print(json.dumps({k: round(v) for k, v in buckets.items()}, ensure_ascii=False, indent=2))
    else:
        total = sum(buckets.values())
        for k, v in sorted(buckets.items(), key=lambda x: -x[1]):
            pct = v / total * 100 if total else 0
            print(f"  {k:<40} ¥{int(v):>12,}  {pct:>5.1f}%")
        print(f"  {'TOTAL':<40} ¥{int(total):>12,}")
    logger.done(TOOL_ID, f"aggregated {len(all_rows)} rows by {args.by}")
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
