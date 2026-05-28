"""sale-mail-retry-manager — Resend バウンス／失敗の retry キュー.

Resend で failed email を抽出し、別アドレスへ手動 retry を支援。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-mail-retry-manager"
RESEND_API = "https://api.resend.com"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale mail-retry-manager")
    p.add_argument("--api-key")
    p.add_argument("--queue", default=str(Path.home() / ".config/emocute/mail_retry.json"))
    p.add_argument("action", choices=["scan", "list", "retry", "drop"])
    p.add_argument("--email-id", help="for retry/drop")
    p.add_argument("--new-to", help="for retry — new recipient")
    return p


def load_q(path: Path) -> list[dict]:
    return json.loads(path.read_text()) if path.exists() else []


def save_q(path: Path, q: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(q, indent=2, ensure_ascii=False))


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
    qpath = Path(args.queue).expanduser().resolve()
    headers = {"Authorization": f"Bearer {key}"}
    q = load_q(qpath)

    if args.action == "scan":
        r = httpx.get(f"{RESEND_API}/emails", headers=headers, timeout=30)
        if r.status_code != 200:
            logger.error(TOOL_ID, f"resend {r.status_code}")
            return 3
        failed = [e for e in r.json().get("data", [])
                  if e.get("last_event") in {"bounced", "failed", "complained"}]
        existing_ids = {x["id"] for x in q}
        added = 0
        for e in failed:
            if e["id"] not in existing_ids:
                q.append({"id": e["id"], "to": e.get("to", []),
                          "subject": e.get("subject", ""),
                          "last_event": e.get("last_event"),
                          "status": "pending"})
                added += 1
        save_q(qpath, q)
        print(f"scan: +{added}, queue size {len(q)}")
        logger.done(TOOL_ID, f"scan +{added}")
    elif args.action == "list":
        for x in q:
            print(f"  [{x['status']}] {x['id'][:10]}  {x['last_event']}  {x['to']}  {x['subject'][:40]}")
        print(f"\ntotal: {len(q)}")
    elif args.action == "drop":
        if not args.email_id:
            logger.error(TOOL_ID, "--email-id required")
            return 2
        q = [x for x in q if x["id"] != args.email_id]
        save_q(qpath, q)
        print(f"✅ dropped {args.email_id}")
    elif args.action == "retry":
        if not args.email_id or not args.new_to:
            logger.error(TOOL_ID, "--email-id and --new-to required")
            return 2
        item = next((x for x in q if x["id"] == args.email_id), None)
        if not item:
            logger.error(TOOL_ID, "id not in queue")
            return 2
        # 元 email を取得 → 新 to で再送
        r = httpx.get(f"{RESEND_API}/emails/{args.email_id}", headers=headers, timeout=30)
        if r.status_code != 200:
            logger.error(TOOL_ID, f"resend get {r.status_code}")
            return 3
        body = r.json()
        new_payload = {
            "from": body.get("from"),
            "to": [args.new_to],
            "subject": body.get("subject"),
            "html": body.get("html", ""),
            "text": body.get("text", ""),
        }
        r2 = httpx.post(f"{RESEND_API}/emails", json=new_payload, headers=headers, timeout=30)
        if r2.status_code not in (200, 201, 202):
            logger.error(TOOL_ID, f"resend post {r2.status_code}: {r2.text[:200]}")
            return 3
        item["status"] = f"retried_to_{args.new_to}"
        save_q(qpath, q)
        print(f"✅ retried {args.email_id} → {args.new_to}")
        logger.done(TOOL_ID, f"retry -> {args.new_to}")
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
