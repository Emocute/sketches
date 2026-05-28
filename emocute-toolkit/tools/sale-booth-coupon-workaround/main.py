"""sale-booth-coupon-workaround — BOOTH のクーポン機能不在を補う代替案計画.

`booth_coupon_secret` 準拠 (BOOTH に標準クーポン機能なし)。「価格を一時下げる」
「限定 URL のシークレット商品」「pixiv FANBOX 経由特典」など複数代替案を比較。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-booth-coupon-workaround"

OPTIONS = {
    "price_drop":     {"effort": "low",   "scope": "全員",   "stealth": "✗", "note": "値下げ告知すると過去購入者が不公平を感じる (silent_price_restore_inquiry)"},
    "secret_url":     {"effort": "med",   "scope": "URL 持ち", "stealth": "○", "note": "シークレット商品で URL 直リンクのみ可"},
    "fanbox_perk":    {"effort": "high",  "scope": "FANBOX 会員", "stealth": "○", "note": "pixivFANBOX 支援者向けに DL コード配布"},
    "booth_apps":     {"effort": "high",  "scope": "契約者", "stealth": "○", "note": "BOOTH Apps 契約で API 経由クーポン (有料)"},
    "stripe_direct":  {"effort": "med",   "scope": "Site",   "stealth": "○", "note": "Site 直販なら Stripe で coupon 機能フル"},
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale booth-coupon-workaround")
    p.add_argument("--list", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    print("BOOTH クーポン代替案:")
    print(f"{'option':<16} {'effort':<7} {'scope':<14} {'stealth':<8} note")
    print("-" * 90)
    for k, v in OPTIONS.items():
        print(f"{k:<16} {v['effort']:<7} {v['scope']:<14} {v['stealth']:<8} {v['note']}")
    print("\n推奨: secret_url (低工数+stealthy) または stripe_direct (Site 直販リソース活用)")
    logger.done(TOOL_ID, f"options: {len(OPTIONS)}")
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
