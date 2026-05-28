"""site-schema-org-inject — schema.org JSON-LD 生成 (MusicAlbum / Product).

各販売物の YAML から MusicAlbum / Product の schema.org JSON-LD を生成、
Nuxt 側で <script type="application/ld+json"> として埋め込む。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "site-schema-org-inject"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site schema-org-inject")
    p.add_argument("kind", choices=["MusicAlbum", "Product"])
    p.add_argument("--name", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--image")
    p.add_argument("--price-jpy", type=int)
    p.add_argument("--release-date")
    return p


def run(args: argparse.Namespace) -> int:
    ld: dict = {
        "@context": "https://schema.org",
        "@type": args.kind,
        "name": args.name,
        "url": args.url,
    }
    if args.image:
        ld["image"] = args.image
    if args.kind == "MusicAlbum":
        ld["byArtist"] = {"@type": "MusicGroup", "name": "Emocute"}
        if args.release_date:
            ld["datePublished"] = args.release_date
    if args.kind == "Product" and args.price_jpy:
        ld["offers"] = {
            "@type": "Offer",
            "price": str(args.price_jpy),
            "priceCurrency": "JPY",
            "availability": "https://schema.org/InStock",
            "seller": {"@type": "Organization", "name": "Emocute Lab."},
        }
    print(json.dumps(ld, indent=2, ensure_ascii=False))
    logger.done(TOOL_ID, f"jsonld {args.kind}")
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
