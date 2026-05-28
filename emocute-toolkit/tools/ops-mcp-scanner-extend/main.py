"""ops-mcp-scanner-extend — `~/.claude.json` 内 MCP server 設定スキャン.

各 MCP server エントリ・許可コマンド・トランスポート・タイムアウト・
未使用 (log.jsonl に現れない) server を一覧化。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-mcp-scanner-extend"

DEFAULT_CFG = "~/.claude.json"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops mcp-scanner-extend")
    p.add_argument("--cfg", default=DEFAULT_CFG)
    return p


def run(args: argparse.Namespace) -> int:
    cfg = Path(args.cfg).expanduser().resolve()
    if not cfg.exists():
        logger.error(TOOL_ID, f"not found: {cfg}")
        return 2
    try:
        data = json.loads(cfg.read_text())
    except json.JSONDecodeError as e:
        logger.error(TOOL_ID, f"invalid json: {e}")
        return 1
    servers = data.get("mcpServers", {}) or {}
    print(f"mcp servers: {len(servers)}")
    for name, spec in servers.items():
        transport = spec.get("type") or ("stdio" if "command" in spec else "?")
        cmd = spec.get("command", "")
        print(f"  • {name:<32} {transport:<6} {cmd[:60]}")
    logger.done(TOOL_ID, f"mcp servers: {len(servers)}")
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
