"""sale-stripe-meta-builder — Stripe Product/Price のメタ JSON 生成.

販売物 1 つを Stripe で create するための product/price メタ JSON を作成。
description / images / statement_descriptor / metadata.album_id 等を埋める。
Stripe API には別ツールから feed する。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-stripe-meta-builder"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale stripe-meta-builder")
    p.add_argument("--name", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--price-jpy", type=int, required=True)
    p.add_argument("--album-id", required=True)
    p.add_argument("--image-url")
    p.add_argument("-o", "--out")
    return p


def run(args: argparse.Namespace) -> int:
    product = {
        "name": args.name,
        "description": args.description,
        "metadata": {"album_id": args.album_id},
    }
    if args.image_url:
        product["images"] = [args.image_url]
    price = {
        "currency": "jpy",
        "unit_amount": args.price_jpy,
        "metadata": {"album_id": args.album_id},
    }
    payload = {"product": product, "price": price,
               "statement_descriptor": "EMOCUTE LAB"}
    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"✅ wrote {out}")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    logger.done(TOOL_ID, f"stripe meta {args.album_id}")
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
