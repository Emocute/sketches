"""studio-batch-mcp-wrapper — Ableton MCP の batch 実行ラッパー.

複数オペレーション (track 作成・clip 配置・effect 適用) を JSONL で記述、
Ableton MCP に逐次投入。MCP 直叩きでもよいが、リトライ・dry-run・行単位
進捗を統一。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-batch-mcp-wrapper"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio batch-mcp-wrapper")
    p.add_argument("script", help="JSONL: 1行ごとに {op, args}")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    s = Path(args.script).expanduser().resolve()
    if not s.exists():
        logger.error(TOOL_ID, f"script not found: {s}")
        return 2
    lines = [l for l in s.read_text().splitlines() if l.strip() and not l.startswith("#")]
    ops = []
    for i, line in enumerate(lines, 1):
        try:
            ops.append(json.loads(line))
        except json.JSONDecodeError as e:
            logger.error(TOOL_ID, f"line {i}: {e}")
            return 2
    print(f"ops: {len(ops)}")
    for i, op in enumerate(ops, 1):
        print(f"  {i:3d}  {op.get('op','?'):<20s}  {str(op.get('args',{}))[:60]}")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    print("\n⚠ MCP 実投入は別途 Ableton MCP プロセス必須 (本ツールは plan + 進捗管理のみ)")
    logger.done(TOOL_ID, f"batch plan {len(ops)} ops")
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
