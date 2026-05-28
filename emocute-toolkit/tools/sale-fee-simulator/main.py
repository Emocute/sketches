"""sale-fee-simulator — 各販売チャネルの手数料シミュレータ.

BOOTH / Gumroad / itch.io / Stripe direct で手取りがいくらになるかを
販売価格別に出す。`price-fee-simulator` は内部用、こちらは販売判断用。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-fee-simulator"

# 概算 (実料率は要 verify)
CHANNELS = {
    "booth_pixiv":  {"pct": 0.056, "fix_jpy": 22, "note": "5.6% + 22円 (pixivID)"},
    "booth_anon":   {"pct": 0.10,  "fix_jpy": 22, "note": "10% + 22円 (匿名配送)"},
    "gumroad":      {"pct": 0.10,  "fix_usd": 0.50, "note": "10% + $0.50"},
    "itchio":       {"pct": 0.10,  "fix_usd": 0,  "note": "10% (default), 出店者調整可"},
    "stripe_direct":{"pct": 0.036, "fix_jpy": 0,  "note": "3.6%"},
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale fee-simulator")
    p.add_argument("price", type=int, help="販売価格 (JPY)")
    p.add_argument("--usd-rate", type=float, default=155.0)
    p.add_argument("--json", action="store_true")
    return p


def calc(price_jpy: int, ch: dict, usd_rate: float) -> dict:
    fee = price_jpy * ch["pct"]
    fee += ch.get("fix_jpy", 0)
    fee += ch.get("fix_usd", 0) * usd_rate
    take = price_jpy - fee
    return {
        "fee_jpy": round(fee),
        "take_jpy": round(take),
        "take_pct": round(take / price_jpy * 100, 1) if price_jpy else 0,
    }


def run(args: argparse.Namespace) -> int:
    if args.price <= 0:
        logger.error(TOOL_ID, "price must be > 0")
        return 2
    rows = {ch: calc(args.price, info, args.usd_rate)
            for ch, info in CHANNELS.items()}
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"price: ¥{args.price}  (USD rate: ¥{args.usd_rate})")
        print(f"{'channel':<16} {'fee':>8} {'take':>9} {'%':>6}")
        print("-" * 50)
        for ch, r in rows.items():
            print(f"{ch:<16} {r['fee_jpy']:>8} {r['take_jpy']:>9} {r['take_pct']:>5}%")
    logger.done(TOOL_ID, f"sim @ ¥{args.price}")
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
