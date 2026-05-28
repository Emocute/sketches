"""ops-idle-alert — 停止検出時に記号ブロックを表示.

`feedback_idle_alert_pattern` 準拠で停止時は異質な記号ブロックで気付かせる。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-idle-alert"

BLOCK = """
████████████████████████████████
█                              █
█       STOPPED — INPUT?       █
█                              █
████████████████████████████████
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops idle-alert")
    p.add_argument("--reason", default="idle")
    return p


def run(args: argparse.Namespace) -> int:
    print(BLOCK)
    print(f"reason: {args.reason}")
    logger.warn(TOOL_ID, f"idle alert: {args.reason}")
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
