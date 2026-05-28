"""ツール実装テンプレート。

新ツール起こす時は以下を実行:
    cp -r tools/_template tools/<category>-<short_name>
    cd tools/<category>-<short_name>
    # main.py の TOOL_ID を変更、main(argv) を実装

CLI から呼ばれる契約:
    emocute <category> <short_name> [args...]
    → tools/<category>-<short_name>/main.py:main(argv) を呼ぶ
    → 戻り値が exit code（None なら 0）
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

# 兄弟 tools/_shared/ をインポート可能にする
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "_template"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"emocute ... {TOOL_ID}")
    p.add_argument("--apply", action="store_true", help="副作用ある書込を実行（既定 dry-run）")
    p.add_argument("--json", action="store_true", help="machine-readable 出力")
    p.add_argument("--pj", help="対象 PJ 名（省略時は cwd basename）")
    return p


def run(args: argparse.Namespace) -> int:
    logger.info(TOOL_ID, "started", meta={"apply": args.apply})
    # TODO: 実装
    logger.done(TOOL_ID, "stub: not yet implemented")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {e}")
        if not args.json:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
