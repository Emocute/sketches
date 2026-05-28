"""site-keyword-rank-monitor — 指定キーワードの Google 検索順位ログ.

検索 API は使わず DuckDuckGo の HTML スクレイプで「Emocute」等の
ブランド語の順位を観測。週次タイムシリーズで JSONL 蓄積。
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "site-keyword-rank-monitor"


def search_ddg(q: str, target_domain: str) -> int | None:
    """DuckDuckGo HTML 版から結果順位を取得 (簡易)"""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read(300_000).decode("utf-8", errors="ignore")
    except Exception:
        return None
    results = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)
    for i, link in enumerate(results, 1):
        if target_domain in link:
            return i
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site keyword-rank-monitor")
    p.add_argument("--query", required=True, action="append", help="複数指定可")
    p.add_argument("--target-domain", required=True)
    p.add_argument("--log", default="keyword_ranks.jsonl")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    rows = []
    today = dt.date.today().isoformat()
    if not args.apply:
        print(f"[dry-run] queries: {args.query}  target: {args.target_domain}")
        return 0
    for q in args.query:
        rank = search_ddg(q, args.target_domain)
        rows.append({"date": today, "query": q, "rank": rank})
        print(f"  {q!r:<30s} → rank {rank}")
    log = Path(args.log).expanduser().resolve()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"\n✅ appended {len(rows)} rows to {log}")
    logger.done(TOOL_ID, f"rank check {len(rows)}")
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
