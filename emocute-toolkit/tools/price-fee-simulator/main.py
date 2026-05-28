"""price-fee-simulator — 各販売チャネル手数料込みの手取り計算.

BOOTH/Gumroad/itch.io/Stripe 直販 別の手数料率・固定費を反映して
売値→手取りを比較。チャネル選定の意思決定支援。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "price-fee-simulator"

# 概算手数料表（2026-05 時点想定、要 source 確認）
CHANNELS = {
    "booth":      {"rate": 0.0566, "fixed": 0,   "currency": "JPY"},  # 5.6%+22 円相当
    "gumroad":    {"rate": 0.10,   "fixed": 0.30, "currency": "USD"},
    "itch_io":    {"rate": 0.10,   "fixed": 0,   "currency": "USD"},  # creator-set default
    "stripe":     {"rate": 0.036,  "fixed": 0,   "currency": "JPY"},  # JP 3.6%
    "stripe_int": {"rate": 0.044,  "fixed": 0.30, "currency": "USD"}, # 海外 4.4%+$0.30
    "paypal_jp":  {"rate": 0.0349, "fixed": 50,  "currency": "JPY"},
    "kofi":       {"rate": 0.0,    "fixed": 0,   "currency": "USD"},  # Ko-fi base free (Gold 別)
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute price fee-simulator")
    p.add_argument("--price", type=float, required=True, help="売値")
    p.add_argument("--currency", choices=["JPY", "USD"], default="JPY")
    p.add_argument("--channels", default="all", help="csv or 'all'")
    return p


def calc(channel: str, price: float, currency: str) -> dict:
    spec = CHANNELS[channel]
    fee = price * spec["rate"] + spec["fixed"]
    net = price - fee
    return {"channel": channel, "price": price, "fee": round(fee, 2),
            "net": round(net, 2), "net_pct": round(net / price * 100, 1) if price else 0,
            "currency": currency}


def run(args: argparse.Namespace) -> int:
    chs = (list(CHANNELS.keys()) if args.channels == "all"
           else [c.strip() for c in args.channels.split(",")])
    bad = [c for c in chs if c not in CHANNELS]
    if bad:
        logger.error(TOOL_ID, f"unknown channels: {bad}")
        return 2
    sym = "¥" if args.currency == "JPY" else "$"
    print(f"price: {sym}{args.price}  currency: {args.currency}")
    print(f"{'channel':<14} {'fee':>10} {'net':>10} {'net%':>6}")
    print("-" * 44)
    rows = []
    for c in chs:
        r = calc(c, args.price, args.currency)
        rows.append(r)
        print(f"{c:<14} {sym}{r['fee']:>9.2f} {sym}{r['net']:>9.2f} {r['net_pct']:>5.1f}%")
    best = max(rows, key=lambda x: x["net"])
    print(f"\n  best: {best['channel']} ({sym}{best['net']:.2f} net)")
    logger.done(TOOL_ID, f"sim {len(rows)} channels, best={best['channel']}")
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
