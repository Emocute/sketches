"""sale-confirm-mail-dashboard — Resend 配信履歴ダッシュボード.

Resend API で送信履歴を取得し、status (delivered/bounced/complained) を集計。
購入後の DL リンクメール到達率を把握。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-confirm-mail-dashboard"
RESEND_API = "https://api.resend.com"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale confirm-mail-dashboard")
    p.add_argument("--api-key", help="$RESEND_API_KEY")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    try:
        import httpx
    except ImportError:
        logger.error(TOOL_ID, "pip install httpx")
        return 3
    key = args.api_key or os.environ.get("RESEND_API_KEY")
    if not key:
        logger.error(TOOL_ID, "RESEND_API_KEY required")
        return 2
    headers = {"Authorization": f"Bearer {key}"}
    # Resend list emails (latest 100)
    r = httpx.get(f"{RESEND_API}/emails", headers=headers, timeout=30)
    if r.status_code != 200:
        logger.error(TOOL_ID, f"Resend API {r.status_code}: {r.text[:200]}")
        return 3
    data = r.json().get("data", [])
    # 集計
    counts: dict[str, int] = {}
    for e in data:
        status = e.get("last_event", "unknown")
        counts[status] = counts.get(status, 0) + 1
    total = sum(counts.values())
    delivered = counts.get("delivered", 0)
    bounced = counts.get("bounced", 0) + counts.get("complained", 0)

    if args.json:
        print(json.dumps({"total": total, "counts": counts}, indent=2))
    else:
        print(f"total emails (last 100): {total}")
        for s, n in sorted(counts.items(), key=lambda x: -x[1]):
            pct = n / total * 100 if total else 0
            print(f"  {s:<15} {n:>4}  ({pct:>5.1f}%)")
        if total:
            rate = delivered / total * 100
            print(f"\n  delivery rate: {rate:.1f}%")
            if bounced:
                print(f"  ⚠ {bounced} bounced/complained — check sender reputation")
    logger.done(TOOL_ID, f"resend {total} emails, delivery={delivered}")
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
