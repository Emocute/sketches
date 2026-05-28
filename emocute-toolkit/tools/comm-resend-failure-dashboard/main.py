"""comm-resend-failure-dashboard — Resend 送信失敗ダッシュボード.

`project_emocutelab_email_send_resend` 準拠。Resend API logs 取得は dry-run のみ
(`feedback_resend_full_access_for_audiences` で Full access 必須)、本ツールは
env-var 存在チェック + plan を出力。
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "comm-resend-failure-dashboard"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute comm resend-failure-dashboard")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        logger.error(TOOL_ID, "RESEND_API_KEY not set")
        return 2
    print(f"RESEND_API_KEY: ***{key[-4:]}")
    print("plan:")
    print("  GET https://api.resend.com/emails?limit=100")
    print("  filter status in (bounced, complained, failed)")
    print("  aggregate by domain + reason")
    if not args.apply:
        print("[dry-run]")
        return 0
    print("(実装: api.resend.com 呼び出しは Site/Sale 側で行う想定。本 CLI は trigger のみ)")
    logger.done(TOOL_ID, "resend dashboard skeleton")
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
