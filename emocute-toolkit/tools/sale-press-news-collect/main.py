"""sale-press-news-collect — 「Emocute」「emocutelab」言及記事を収集.

メディア記事 URL のリストから titleとexcerpt を抽出、自社プレス集約 md。
実 fetch は urllib.request、HTML から <title> と meta description を抜く。
"""
from __future__ import annotations
import argparse
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-press-news-collect"


def fetch_meta(url: str, timeout: int = 10) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (emocute-toolkit)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read(200_000).decode("utf-8", errors="ignore")
    except Exception as e:
        return {"url": url, "error": str(e)}
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.IGNORECASE)
    return {
        "url": url,
        "title": title_m.group(1).strip() if title_m else "",
        "description": desc_m.group(1).strip() if desc_m else "",
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale press-news-collect")
    p.add_argument("urls_file", help="1 行 1 URL")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.urls_file).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    urls = [l.strip() for l in src.read_text().splitlines() if l.strip()]
    print(f"urls: {len(urls)}")
    if not args.apply:
        for u in urls[:10]:
            print(f"  • {u}")
        print("\n[dry-run]")
        return 0
    entries = []
    for u in urls:
        meta = fetch_meta(u)
        entries.append(meta)
        if "error" in meta:
            print(f"  ⚠ {u}: {meta['error']}")
        else:
            print(f"  ✅ {meta['title'][:60]}")
    out = Path(args.out).expanduser().resolve()
    md_parts = ["# Press / News mentions\n"]
    for e in entries:
        if "error" in e:
            continue
        md_parts.append(f"\n## [{e['title']}]({e['url']})\n\n{e['description']}\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md_parts))
    print(f"\n✅ wrote {out}")
    logger.done(TOOL_ID, f"press: {len(entries)} entries")
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
