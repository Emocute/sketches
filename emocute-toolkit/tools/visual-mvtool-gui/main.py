"""visual-mvtool-gui — mvtool.py の薄い GUI ラッパー仕様生成.

Tkinter ベースのファイル選択 + プリセット切替 GUI スケッチ。本ツールは
仕様 YAML 出力のみ (GUI 本体は別実装)。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-mvtool-gui"

PRESETS = {
    "lyric_mv_basic":     {"lyrics": True, "bg_video": True, "logo": False},
    "lyric_mv_with_logo": {"lyrics": True, "bg_video": True, "logo": True},
    "kara_only":          {"lyrics": True, "bg_video": False, "logo": False},
    "loop_visual_only":   {"lyrics": False, "bg_video": True, "logo": True},
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual mvtool-gui")
    p.add_argument("--list-presets", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps(PRESETS, indent=2, ensure_ascii=False))
    else:
        print("mvtool GUI プリセット一覧:")
        for k, v in PRESETS.items():
            tags = ", ".join(f"{kk}={vv}" for kk, vv in v.items())
            print(f"  • {k:<24s}  {tags}")
        print(f"\n本ツールは仕様提示のみ。GUI 本体は Visual/mvtool.py に統合実装が必要。")
    logger.done(TOOL_ID, f"presets: {len(PRESETS)}")
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
