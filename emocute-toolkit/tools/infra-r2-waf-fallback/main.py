"""infra-r2-waf-fallback — Cloudflare R2/Dashboard WAF 403 検出と fallback 案.

CF Dashboard `/api/v4/` POST が WAF で 403 になりがち。
S3-compatible API (R2 access keys) または UI 操作への切替提案を出す。
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "infra-r2-waf-fallback"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute infra r2-waf-fallback")
    p.add_argument("--check-endpoint", default="https://api.cloudflare.com/client/v4/user")
    p.add_argument("--account-id", help="for R2 S3 endpoint test")
    p.add_argument("--bucket", help="R2 bucket name for fallback test")
    return p


def run(args: argparse.Namespace) -> int:
    try:
        import httpx
    except ImportError:
        logger.error(TOOL_ID, "pip install httpx")
        return 3

    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        print("⚠ CLOUDFLARE_API_TOKEN env not set")
    else:
        r = httpx.get(args.check_endpoint,
                      headers={"Authorization": f"Bearer {token}"}, timeout=20)
        if r.status_code == 403:
            print(f"❌ CF API 403 — WAF block confirmed")
            print("  → fallback options:")
            print("    1) R2: use S3-compatible endpoint with R2 access keys")
            print("       export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY")
            print(f"       boto3.client('s3', endpoint_url='https://<acc>.r2.cloudflarestorage.com')")
            print("    2) Dashboard UI: open Chrome + osascript click")
            print(f"       open 'https://dash.cloudflare.com/<acc>/r2/buckets/{args.bucket or '<bucket>'}'")
            logger.warn(TOOL_ID, "WAF 403, fallback required")
            return 1
        elif r.status_code == 200:
            print(f"✅ CF API reachable (status 200)")
            logger.done(TOOL_ID, "CF OK")
            return 0
        else:
            print(f"⚠ CF API status {r.status_code}: {r.text[:200]}")
            return 1

    if args.account_id and args.bucket:
        # S3 test
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
        if not access_key or not secret:
            print("⚠ AWS_ACCESS_KEY_ID / SECRET not set for R2 S3 fallback test")
            return 1
        try:
            import boto3  # type: ignore
        except ImportError:
            print("⚠ pip install boto3 for S3 fallback test")
            return 1
        s3 = boto3.client(
            "s3", endpoint_url=f"https://{args.account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key, aws_secret_access_key=secret,
            region_name="auto")
        try:
            objs = s3.list_objects_v2(Bucket=args.bucket, MaxKeys=5)
            print(f"✅ R2 S3 fallback OK: {objs.get('KeyCount', 0)} objects sample")
            logger.done(TOOL_ID, f"S3 fallback OK: {args.bucket}")
        except Exception as e:
            print(f"❌ R2 S3 fallback failed: {e}")
            return 1
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
