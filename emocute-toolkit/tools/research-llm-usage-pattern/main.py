"""research-llm-usage-pattern — LLM 利用パターン集計.

`~/.claude/notifications/log.jsonl` から PJ ごとの利用頻度・時間帯分布・
peak hour を算出。
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "research-llm-usage-pattern"

DEFAULT_LOG = "~/.claude/notifications/log.jsonl"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute research llm-usage-pattern")
    p.add_argument("--log", default=DEFAULT_LOG)
    return p


def run(args: argparse.Namespace) -> int:
    log = Path(args.log).expanduser().resolve()
    if not log.exists():
        logger.error(TOOL_ID, f"not found: {log}")
        return 2
    hours: Counter[int] = Counter()
    pjs: Counter[str] = Counter()
    total = 0
    for line in log.read_text(errors="ignore").splitlines():
        try:
            j = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = j.get("ts")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                hours[dt.hour] += 1
            except ValueError:
                pass
        pjs[j.get("pj", "?")] += 1
        total += 1
    print(f"total events: {total}")
    print("\nhourly distribution:")
    for h in range(24):
        bar = "#" * min(40, hours[h] // max(1, total // 200))
        print(f"  {h:>2}h  {hours[h]:>5}  {bar}")
    print("\ntop pj:")
    for pj, n in pjs.most_common(10):
        print(f"  {n:>5}  {pj}")
    logger.done(TOOL_ID, f"usage: {total} events")
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
