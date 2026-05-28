"""site-dl-integrity — Site products × R2 ファイル一覧 突合.

spec: registry/site/site-dl-integrity.yaml
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import config, logger  # noqa: E402

TOOL_ID = "site-dl-integrity"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site dl-integrity")
    p.add_argument("--json", action="store_true")
    p.add_argument("--notify", action="store_true")
    p.add_argument("--bucket", help="R2 bucket name (default: cred.r2.bucket)")
    return p


def load_products_from_site() -> list[dict]:
    """Site/data/products.ts or .json から products を抽出（ベストエフォート）."""
    try:
        site_root = config.pj_path("Site")
    except KeyError:
        return []
    candidates = [
        site_root / "data" / "products.json",
        site_root / "data" / "products.ts",
        site_root / "data" / "albums.ts",
    ]
    out: list[dict] = []
    for c in candidates:
        if not c.exists():
            continue
        text = c.read_text(encoding="utf-8", errors="ignore")
        if c.suffix == ".json":
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    out.extend(data)
                elif isinstance(data, dict) and "products" in data:
                    out.extend(data["products"])
            except json.JSONDecodeError:
                pass
            continue
        # TS から: r2_zip_key: '...', preview_mp3_key: '...', id: '...'
        for m in re.finditer(
            r"id\s*:\s*['\"]([^'\"]+)['\"][\s\S]*?"
            r"(?:r2_zip_key|zipKey|zip_key)\s*:\s*['\"]([^'\"]+)['\"]"
            r"(?:[\s\S]*?(?:preview_mp3_key|previewKey|preview_key)\s*:\s*['\"]([^'\"]+)['\"])?",
            text,
        ):
            out.append({
                "id": m.group(1),
                "r2_zip_key": m.group(2),
                "preview_mp3_key": m.group(3),
            })
    return out


def list_r2_objects(bucket: str | None) -> set[str] | None:
    """R2 list-objects via boto3 (S3 互換)."""
    access = config.cred("r2.access_key_id")
    secret = config.cred("r2.secret_access_key")
    account = config.cred("r2.account_id")
    bucket = bucket or config.cred("r2.bucket")
    if not (access and secret and account and bucket):
        return None
    try:
        import boto3
        from botocore.client import Config as BotoConfig
    except ImportError:
        logger.warn(TOOL_ID, "boto3 not installed; cannot query R2")
        return None
    endpoint = f"https://{account}.r2.cloudflarestorage.com"
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )
    keys: set[str] = set()
    token = None
    while True:
        kwargs = {"Bucket": bucket, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []) or []:
            keys.add(obj["Key"])
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def notify(title: str, msg: str) -> None:
    bin_ = "/opt/homebrew/bin/terminal-notifier"
    if not Path(bin_).exists():
        return
    try:
        subprocess.run([bin_, "-title", title, "-message", msg, "-sound", "Glass"],
                       check=False, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run(args: argparse.Namespace) -> int:
    products = load_products_from_site()
    if not products:
        logger.error(TOOL_ID, "no products found in Site/data/*")
        print("❌ Site/data/ から products を読めない")
        return 2

    r2_keys = list_r2_objects(args.bucket)
    if r2_keys is None:
        logger.warn(TOOL_ID, "R2 credentials missing; skipping bucket comparison")
        print("⚠️  R2 credentials 未設定。R2 突合スキップ、products のキー有無のみ報告")

    findings = []
    for p in products:
        pid = p.get("id") or p.get("name") or "(unknown)"
        zip_key = p.get("r2_zip_key") or p.get("zipKey") or p.get("zip_key")
        prev_key = p.get("preview_mp3_key") or p.get("previewKey") or p.get("preview_key")
        record = {"id": pid, "zip_key": zip_key, "preview_key": prev_key,
                  "zip_present": None, "preview_present": None,
                  "issues": []}
        if not zip_key:
            record["issues"].append("missing r2_zip_key in product entry")
        if r2_keys is not None:
            if zip_key:
                record["zip_present"] = zip_key in r2_keys
                if not record["zip_present"]:
                    record["issues"].append(f"zip not in R2: {zip_key}")
            if prev_key:
                record["preview_present"] = prev_key in r2_keys
                if not record["preview_present"]:
                    record["issues"].append(f"preview not in R2: {prev_key}")
        record["is_ready_for_sale"] = (
            bool(zip_key)
            and (record["zip_present"] is not False)
            and not any("zip not in" in i for i in record["issues"])
        )
        findings.append(record)

    err_records = [f for f in findings if any("zip not in" in i or "missing r2_zip_key" in i for i in f["issues"])]
    warn_records = [f for f in findings if f["issues"] and f not in err_records]

    if args.json:
        print(json.dumps({"products": findings,
                          "errors": len(err_records),
                          "warnings": len(warn_records)},
                         ensure_ascii=False, indent=2))
    else:
        print(f"{'id':<30} {'zip':<8} {'preview':<8} {'sale':<6} issues")
        print("-" * 80)
        for f in findings:
            zp = "?" if f["zip_present"] is None else ("✓" if f["zip_present"] else "✗")
            pp = "?" if f["preview_present"] is None else ("✓" if f["preview_present"] else "✗")
            sale = "✓" if f["is_ready_for_sale"] else "✗"
            issues = "; ".join(f["issues"])[:50]
            print(f"{f['id'][:28]:<30} {zp:<8} {pp:<8} {sale:<6} {issues}")
        print()
        if err_records:
            print(f"❌ {len(err_records)} products NOT ready for sale")
        if warn_records:
            print(f"⚠️  {len(warn_records)} products with minor issues")

    if err_records:
        logger.error(TOOL_ID, f"DL integrity NG: {len(err_records)} products")
        if args.notify:
            notify("Site DL integrity NG", f"{len(err_records)} products not ready")
        return 2
    if warn_records:
        logger.warn(TOOL_ID, f"DL integrity warn: {len(warn_records)}")
        return 1
    logger.done(TOOL_ID, f"DL integrity OK: {len(findings)} products")
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
