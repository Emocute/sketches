"""infra-cf-dns-ssl-monitor — Cloudflare DNS+SSL 監視.

`emocutelab.com` 等のドメインの SSL 有効期限 + A/CNAME 解決 +
HTTPS 接続を ssl/socket で確認。証明書 30 日以内に期限切れなら warn。
"""
from __future__ import annotations
import argparse
import socket
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "infra-cf-dns-ssl-monitor"

WARN_DAYS = 30


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute infra cf-dns-ssl-monitor")
    p.add_argument("domains", nargs="+")
    return p


def check(domain: str) -> dict:
    out = {"domain": domain}
    try:
        out["ip"] = socket.gethostbyname(domain)
    except OSError as e:
        out["error"] = f"dns: {e}"
        return out
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
        not_after = cert.get("notAfter", "")
        if not_after:
            exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days = (exp - datetime.now(timezone.utc)).days
            out["expires_in_days"] = days
            out["expires_at"] = exp.isoformat()
    except Exception as e:
        out["error"] = f"ssl: {e}"
    return out


def run(args: argparse.Namespace) -> int:
    warned = 0
    for d in args.domains:
        r = check(d)
        print(f"\n=== {d} ===")
        for k, v in r.items():
            print(f"  {k:<18} {v}")
        days = r.get("expires_in_days")
        if isinstance(days, int) and days < WARN_DAYS:
            print(f"  ⚠ cert expires in {days} days")
            warned += 1
    if warned:
        logger.warn(TOOL_ID, f"{warned} domain(s) need renewal")
        return 1
    logger.done(TOOL_ID, f"checked {len(args.domains)} domains")
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
