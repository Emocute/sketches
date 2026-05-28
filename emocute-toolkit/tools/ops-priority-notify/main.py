"""ops-priority-notify — 通知システムに priority 付きで送信.

`~/.claude/notifications/log.jsonl` に priority 付きで追記し、
critical/high は terminal-notifier + 音、low はログのみ。
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-priority-notify"
LOG = Path.home() / ".claude/notifications/log.jsonl"

PRIORITY_CONFIG = {
    "critical": {"sound": "/System/Library/Sounds/Sosumi.aiff", "vol": 0.7, "popup": True},
    "high":     {"sound": "/System/Library/Sounds/Glass.aiff",  "vol": 0.5, "popup": True},
    "med":      {"sound": "/System/Library/Sounds/Tink.aiff",   "vol": 0.3, "popup": True},
    "low":      {"sound": None,                                  "vol": 0,   "popup": False},
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops priority-notify")
    p.add_argument("message")
    p.add_argument("--priority", choices=list(PRIORITY_CONFIG.keys()), default="med")
    p.add_argument("--pj", default="ops")
    p.add_argument("--title", default="emocute")
    return p


def run(args: argparse.Namespace) -> int:
    cfg = PRIORITY_CONFIG[args.priority]
    # log
    LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": dt.datetime.now().isoformat(timespec="seconds"),
             "type": args.priority, "pj": args.pj,
             "message": args.message}
    with LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # sound
    if cfg["sound"]:
        subprocess.run(["afplay", "-v", str(cfg["vol"]), cfg["sound"]],
                       check=False)
    # popup
    if cfg["popup"]:
        tn = "/opt/homebrew/bin/terminal-notifier"
        if Path(tn).exists():
            subprocess.run([tn, "-title", args.title,
                            "-subtitle", f"[{args.priority}] {args.pj}",
                            "-message", args.message[:200]], check=False)
    print(f"✅ [{args.priority}] {args.message[:80]}")
    logger.done(TOOL_ID, f"notify {args.priority}: {args.pj}")
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
