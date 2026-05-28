"""sale-utm-shortener — UTM 付き販売 URL の短縮+一覧化.

URL に utm_source/medium/campaign を付けた完全 URL → 任意の slug に
shorten。Site の /go/<slug> エンドポイント側で実 URL に redirect する想定。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-utm-shortener"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale utm-shortener")
    sub = p.add_subparsers(dest="cmd", required=True)
    sb = sub.add_parser("build")
    sb.add_argument("url")
    sb.add_argument("--source", required=True)
    sb.add_argument("--medium", default="referral")
    sb.add_argument("--campaign", required=True)
    sb.add_argument("--slug", required=True)
    sb.add_argument("--db", default="utm_slugs.json")
    sb.add_argument("--apply", action="store_true")
    sl = sub.add_parser("list")
    sl.add_argument("--db", default="utm_slugs.json")
    return p


def run(args: argparse.Namespace) -> int:
    db_path = Path(args.db).expanduser().resolve()
    db = json.loads(db_path.read_text()) if db_path.exists() else {}
    if args.cmd == "list":
        for slug, info in db.items():
            print(f"  /go/{slug:<20s}  → {info['url']}")
        print(f"\n{len(db)} slugs")
        return 0
    sep = "&" if "?" in args.url else "?"
    full = f"{args.url}{sep}utm_source={args.source}&utm_medium={args.medium}&utm_campaign={args.campaign}"
    info = {"url": full, "source": args.source, "campaign": args.campaign}
    print(f"slug:  /go/{args.slug}")
    print(f"  → {full}")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    if args.slug in db:
        logger.error(TOOL_ID, f"slug already exists: {args.slug}")
        return 1
    db[args.slug] = info
    db_path.write_text(json.dumps(db, indent=2, ensure_ascii=False))
    print(f"✅ saved → {db_path}")
    logger.done(TOOL_ID, f"slug /go/{args.slug}")
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
