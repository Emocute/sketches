"""site-sitemap-rebuild — pages/ から sitemap.xml を再生成.

pages/ 配下を再帰探索、JP/EN 両言語のページを XML として書き出し。
"""
from __future__ import annotations
import argparse
import sys
import xml.sax.saxutils as sx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "site-sitemap-rebuild"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site sitemap-rebuild")
    p.add_argument("site_root")
    p.add_argument("--base-url", required=True)
    p.add_argument("-o", "--out", default="public/sitemap.xml")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.site_root).expanduser().resolve()
    pages = root / "pages"
    if not pages.exists():
        logger.error(TOOL_ID, "no pages/")
        return 2
    routes = []
    for p in pages.rglob("*.vue"):
        rel = p.relative_to(pages).with_suffix("")
        parts = [x for x in rel.parts if x != "index"]
        route = "/" + "/".join(parts)
        if "[" not in route:  # 動的 route スキップ
            routes.append(route)
    routes = sorted(set(routes))
    out_path = root / args.out if not Path(args.out).is_absolute() else Path(args.out)
    print(f"routes: {len(routes)}  → {out_path}")
    if not args.apply:
        for r in routes[:15]:
            print(f"  {args.base_url}{r}")
        print("\n[dry-run]")
        return 0
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for r in routes:
        loc = sx.escape(f"{args.base_url}{r}")
        lines.append(f"  <url><loc>{loc}</loc></url>")
    lines.append("</urlset>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    print(f"✅ wrote {out_path}")
    logger.done(TOOL_ID, f"sitemap {len(routes)} urls")
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
