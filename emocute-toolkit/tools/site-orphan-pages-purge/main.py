"""site-orphan-pages-purge — Site の孤立ページ検出.

`project_site_orphan_pages_purged_2026-05-28` 準拠。ナビ/フッター/sitemap.xml
に出てこないが pages/ に残っている `.vue` を孤立として一覧化。
削除は手動 (NEVER auto-delete)。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "site-orphan-pages-purge"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site orphan-pages-purge")
    p.add_argument("site_root", help="Nuxt site root")
    return p


def page_to_route(p: Path, pages_dir: Path) -> str:
    rel = p.relative_to(pages_dir).with_suffix("")
    parts = []
    for x in rel.parts:
        if x == "index":
            continue
        parts.append(x)
    return "/" + "/".join(parts) if parts else "/"


def run(args: argparse.Namespace) -> int:
    root = Path(args.site_root).expanduser().resolve()
    pages_dir = root / "pages"
    if not pages_dir.exists():
        logger.error(TOOL_ID, f"no pages/ in {root}")
        return 2
    routes = set()
    for p in pages_dir.rglob("*.vue"):
        routes.add(page_to_route(p, pages_dir))
    referenced = set()
    for f in root.rglob("*.vue"):
        if pages_dir not in f.parents and f != pages_dir:
            pass
        text = f.read_text(errors="ignore")
        for m in re.finditer(r'(?:to|href)=["\'](/[^"\']*)["\']', text):
            referenced.add(m.group(1).rstrip("/") or "/")
    sitemap = root / "public" / "sitemap.xml"
    if sitemap.exists():
        for m in re.finditer(r"<loc>https?://[^/]+([^<]+)</loc>", sitemap.read_text(errors="ignore")):
            referenced.add(m.group(1).rstrip("/") or "/")
    orphans = sorted(routes - referenced - {"/"})
    print(f"total routes: {len(routes)}")
    print(f"referenced:   {len(routes & referenced)}")
    print(f"orphans:      {len(orphans)}")
    for o in orphans:
        print(f"  ⚠ {o}")
    print("\n⚠ 削除は手動。 _archive/loose_<date>/ に退避してから NEVER rm")
    logger.done(TOOL_ID, f"orphans: {len(orphans)}")
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
