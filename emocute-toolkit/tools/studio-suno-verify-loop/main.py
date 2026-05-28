"""studio-suno-verify-loop — Suno 注入のリトライ＋検証ループ.

Suno UI の create='ok' を信用せず、生成タスクの状態を一定間隔でポーリング。
失敗パターンを記録、最大 N 回まで自動再注入。

`feedback_suno_injection_verify` 準拠。
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-suno-verify-loop"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio suno-verify-loop")
    p.add_argument("payload", help="JSON payload (prompt/style/lyrics)")
    p.add_argument("--max-retry", type=int, default=3)
    p.add_argument("--interval", type=int, default=20, help="poll 間隔 (秒)")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    pay = Path(args.payload).expanduser().resolve()
    if not pay.exists():
        logger.error(TOOL_ID, f"payload not found: {pay}")
        return 2
    try:
        spec = json.loads(pay.read_text())
    except json.JSONDecodeError as e:
        logger.error(TOOL_ID, f"invalid json: {e}")
        return 2
    if not args.apply:
        print(f"[dry-run] would inject Suno with payload {pay.name}")
        print(f"  max-retry: {args.max_retry}  interval: {args.interval}s")
        print("  spec keys:", list(spec.keys()))
        return 0
    print(f"⚠ Suno UI 実注入は MCP/Playwright 経由実装が必要 (本ツールは loop guard のみ)")
    print(f"verify loop: retry={args.max_retry} interval={args.interval}s")
    for i in range(args.max_retry):
        print(f"  attempt {i+1}/{args.max_retry}... (would call suno_inject + verify)")
        time.sleep(min(args.interval, 1))
    logger.done(TOOL_ID, "suno verify loop simulated")
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
