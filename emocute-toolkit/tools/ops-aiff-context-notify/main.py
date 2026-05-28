"""ops-aiff-context-notify — 通知音 1 回再生.

`feedback_task_notification` 準拠で完了=Glass.aiff -v 0.001 1 回。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-aiff-context-notify"

DEFAULT_SOUND = "/System/Library/Sounds/Glass.aiff"
DEFAULT_VOL = 0.001


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops aiff-context-notify")
    p.add_argument("--sound", default=DEFAULT_SOUND)
    p.add_argument("--volume", type=float, default=DEFAULT_VOL)
    return p


def run(args: argparse.Namespace) -> int:
    sp = Path(args.sound)
    if not sp.exists():
        logger.error(TOOL_ID, f"sound not found: {sp}")
        return 2
    subprocess.run(["afplay", "-v", str(args.volume), str(sp)])
    logger.done(TOOL_ID, "notify played")
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
