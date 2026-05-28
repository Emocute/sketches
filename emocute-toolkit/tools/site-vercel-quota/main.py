"""site-vercel-quota — Vercel deploy quota monitor.

spec: registry/site/site-vercel-quota.yaml
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import config, logger  # noqa: E402

TOOL_ID = "site-vercel-quota"

HOBBY_MONTHLY_BUILDS = 100  # 想定上限


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site vercel-quota")
    p.add_argument("--threshold", type=int, default=30,
                   help="残数しきい値 (default 30)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--notify", action="store_true")
    return p


def fetch_deployments_count() -> int | None:
    """Vercel API でチームの当月 deployment 数を取得.

    credentials が無ければ None。CI 環境では env VERCEL_TOKEN も見る。
    """
    import os
    token = config.cred("vercel.token") or os.environ.get("VERCEL_TOKEN")
    team_id = config.cred("vercel.team_id") or os.environ.get("VERCEL_TEAM_ID")
    if not token:
        return None
    try:
        import httpx
    except ImportError:
        logger.warn(TOOL_ID, "httpx not installed; cannot query Vercel API")
        return None

    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    month_start = dt.datetime(now.year, now.month, 1, tzinfo=dt.timezone.utc)
    since_ms = int(month_start.timestamp() * 1000)

    url = "https://api.vercel.com/v6/deployments"
    params = {"since": since_ms, "limit": 100}
    if team_id:
        params["teamId"] = team_id
    headers = {"Authorization": f"Bearer {token}"}

    total = 0
    next_ts = None
    try:
        with httpx.Client(timeout=10.0) as client:
            for _ in range(50):  # safety cap
                p = dict(params)
                if next_ts:
                    p["until"] = next_ts
                r = client.get(url, params=p, headers=headers)
                if r.status_code != 200:
                    logger.warn(TOOL_ID, f"vercel api status={r.status_code}: {r.text[:200]}")
                    return None
                data = r.json()
                deps = data.get("deployments", [])
                total += len(deps)
                pagination = data.get("pagination", {})
                next_ts = pagination.get("next")
                if not next_ts or not deps:
                    break
    except (httpx.HTTPError, OSError) as e:
        logger.warn(TOOL_ID, f"vercel api error: {e}")
        return None
    return total


def count_pending_commits() -> tuple[int, str | None]:
    """Site PJ で push 待ち commit 数."""
    try:
        site_root = config.pj_path("Site")
    except KeyError:
        return 0, None
    if not site_root.exists():
        return 0, None
    proc = subprocess.run(
        ["git", "-C", str(site_root), "log", "@{u}..HEAD", "--oneline"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        return 0, None
    lines = proc.stdout.strip().splitlines()
    return len(lines), proc.stdout.strip()


def notify(title: str, msg: str) -> None:
    bin_ = "/opt/homebrew/bin/terminal-notifier"
    if not Path(bin_).exists():
        return
    try:
        subprocess.run([bin_, "-title", title, "-message", msg, "-sound", "Tink"],
                       check=False, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run(args: argparse.Namespace) -> int:
    used = fetch_deployments_count()
    pending, log = count_pending_commits()

    result = {
        "deployments_this_month": used,
        "monthly_cap_assumed": HOBBY_MONTHLY_BUILDS,
        "remaining_assumed": (HOBBY_MONTHLY_BUILDS - used) if used is not None else None,
        "pending_commits_to_push": pending,
        "threshold": args.threshold,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if used is None:
            print("⚠️  Vercel API unreachable (set credentials.yaml vercel.token or $VERCEL_TOKEN)")
        else:
            remaining = HOBBY_MONTHLY_BUILDS - used
            mark = "⚠️" if remaining < args.threshold else "✅"
            print(f"{mark} this month: {used} deployments  (remaining ~{remaining}/{HOBBY_MONTHLY_BUILDS})")
        if pending > 1:
            print(f"💡 {pending} commits queued on Site main — consider bundling into 1 deploy")
            if log:
                print("---")
                print(log)

    if used is None:
        return 1
    remaining = HOBBY_MONTHLY_BUILDS - used
    if remaining < args.threshold:
        logger.warn(TOOL_ID, f"vercel quota low: {remaining} left (used {used})")
        if args.notify:
            notify("Vercel quota low", f"残 {remaining}/{HOBBY_MONTHLY_BUILDS}")
        return 1
    logger.done(TOOL_ID, f"vercel quota OK: {remaining} left")
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
