"""ops-mcp-usage-log — MCP ツール呼び出し回数の集計.

`~/.claude/notifications/log.jsonl` から MCP 呼び出しイベントを集計し、
ツール別呼び出し回数を表示。
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-mcp-usage-log"

DEFAULT_LOG = "~/.claude/notifications/log.jsonl"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops mcp-usage-log")
    p.add_argument("--log", default=DEFAULT_LOG)
    p.add_argument("--limit", type=int, default=20)
    return p


def run(args: argparse.Namespace) -> int:
    log = Path(args.log).expanduser().resolve()
    if not log.exists():
        logger.error(TOOL_ID, f"not found: {log}")
        return 2
    counts: Counter[str] = Counter()
    for line in log.read_text(errors="ignore").splitlines():
        try:
            j = json.loads(line)
        except json.JSONDecodeError:
            continue
        pj = j.get("pj", "?")
        counts[pj] += 1
    print(f"total events: {sum(counts.values())}")
    print(f"unique pj: {len(counts)}")
    print("\ntop pj:")
    for pj, n in counts.most_common(args.limit):
        print(f"  {n:>6}  {pj}")
    logger.done(TOOL_ID, f"mcp-log: {sum(counts.values())} events")
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
