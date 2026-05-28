"""sale-audience-segmentation — Resend Audiences のセグメント生成.

購入履歴 CSV から「アルバム購入者」「Kagebu 購入者」「両方」等のセグメントを
作成、Resend Audiences API 投入用 JSON を出力。
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

TOOL_ID = "sale-audience-segmentation"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale audience-segmentation")
    p.add_argument("orders_csv", help="email, product_category の CSV")
    p.add_argument("-o", "--out", required=True, help="出力 JSON")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.orders_csv).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    cats: dict[str, set[str]] = defaultdict(set)
    with src.open() as f:
        for row in csv.DictReader(f):
            email = row.get("email", "").strip().lower()
            cat = row.get("product_category", "").strip()
            if email and cat:
                cats[cat].add(email)
    if not cats:
        logger.warn(TOOL_ID, "no categories found")
        return 1
    segments = {}
    for cat, emails in cats.items():
        segments[cat] = sorted(emails)
    cat_list = list(cats.keys())
    if len(cat_list) >= 2:
        c0, c1 = cat_list[0], cat_list[1]
        segments[f"{c0}_and_{c1}"] = sorted(cats[c0] & cats[c1])
        segments[f"{c0}_only"] = sorted(cats[c0] - cats[c1])
    print(f"segments: {len(segments)}")
    for s, emails in segments.items():
        print(f"  {s}: {len(emails)} subs")
    out = Path(args.out).expanduser().resolve()
    if not args.apply:
        print("\n[dry-run]")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(segments, indent=2, ensure_ascii=False))
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"segments: {len(segments)}")
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
