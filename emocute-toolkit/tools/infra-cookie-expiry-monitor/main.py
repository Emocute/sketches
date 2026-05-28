"""infra-cookie-expiry-monitor — Playwright プロファイルの cookie 期限監視.

`~/.claude/playwright-profile/Default/Cookies` (SQLite) の expires_utc を
読み、近日期限切れの session を warn。期限切れ前に再ログイン促進。
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "infra-cookie-expiry-monitor"

DEFAULT_PROFILE = "~/.claude/playwright-profile/Default/Cookies"
WARN_DAYS = 14


def chrome_epoch_to_dt(v: int) -> datetime:
    # Chrome epoch: microseconds since 1601-01-01 UTC
    epoch_start = datetime(1601, 1, 1, tzinfo=timezone.utc)
    return epoch_start + timedelta(microseconds=v)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute infra cookie-expiry-monitor")
    p.add_argument("--db", default=DEFAULT_PROFILE)
    p.add_argument("--hosts", nargs="+", help="filter by host substring")
    return p


def run(args: argparse.Namespace) -> int:
    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        logger.error(TOOL_ID, f"cookies db not found: {db_path}")
        return 2
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute("SELECT host_key, name, expires_utc FROM cookies").fetchall()
        conn.close()
    except sqlite3.Error as e:
        logger.error(TOOL_ID, f"db read failed (locked?): {e}")
        return 3
    now = datetime.now(timezone.utc)
    soon = []
    for host, name, expires in rows:
        if not expires:
            continue
        exp = chrome_epoch_to_dt(expires)
        days = (exp - now).days
        if args.hosts and not any(h in host for h in args.hosts):
            continue
        if 0 <= days <= WARN_DAYS:
            soon.append((host, name, days))
    print(f"total cookies: {len(rows)}  expiring soon: {len(soon)}")
    for host, name, days in soon[:30]:
        print(f"  ⏳ {days:>3}d  {host}  {name}")
    if soon:
        logger.warn(TOOL_ID, f"{len(soon)} cookies expire within {WARN_DAYS}d")
        return 1
    logger.done(TOOL_ID, "no near-expiry cookies")
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
