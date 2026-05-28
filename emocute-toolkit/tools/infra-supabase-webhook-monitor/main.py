"""infra-supabase-webhook-monitor — Supabase webhook の動作確認.

Supabase Management API で webhook 一覧と最近の delivery 状況を確認。
Site の購入 hook 等が動いてるか即時把握。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "infra-supabase-webhook-monitor"
API = "https://api.supabase.com"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute infra supabase-webhook-monitor")
    p.add_argument("--project-ref", required=True)
    p.add_argument("--token", help="$SUPABASE_ACCESS_TOKEN")
    return p


def run(args: argparse.Namespace) -> int:
    try:
        import httpx
    except ImportError:
        logger.error(TOOL_ID, "pip install httpx")
        return 3
    token = args.token or os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        logger.error(TOOL_ID, "SUPABASE_ACCESS_TOKEN required")
        return 2
    headers = {"Authorization": f"Bearer {token}"}
    # function-hooks や webhooks の取得 (Management API)
    url = f"{API}/v1/projects/{args.project_ref}/functions"
    r = httpx.get(url, headers=headers, timeout=20)
    if r.status_code == 401:
        logger.error(TOOL_ID, "401 unauthorized — token expired?")
        return 3
    if r.status_code != 200:
        logger.error(TOOL_ID, f"API {r.status_code}: {r.text[:200]}")
        return 3
    functions = r.json()
    print(f"functions: {len(functions)}")
    for fn in functions[:20]:
        name = fn.get("name") or fn.get("slug", "(?)")
        status = fn.get("status", "?")
        ver = fn.get("version", "?")
        print(f"  {name:<30} {status:<10} v{ver}")
    logger.done(TOOL_ID, f"{len(functions)} functions")
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
