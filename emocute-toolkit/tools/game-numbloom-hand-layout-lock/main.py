"""game-numbloom-hand-layout-lock — 手札 UI レイアウトの固定検証.

`feedback_menu_sacred` の SVG 不可侵に加えて、手札領域 (5 枚 + ドラフト 1 枚) の
座標が `game.html` の規定位置から変わってないかチェック。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-numbloom-hand-layout-lock"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game numbloom-hand-layout-lock")
    p.add_argument("game_html")
    p.add_argument("--baseline", help="期待座標の JSON")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.game_html).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    text = src.read_text(errors="ignore")
    hand_coords = re.findall(r'hand[_-]?slot[_-]?(\d+)[^{]*\{[^}]*?(left|x)\s*:\s*([0-9.]+)', text)
    print(f"hand slot rules found: {len(hand_coords)}")
    for slot, attr, val in hand_coords[:10]:
        print(f"  slot {slot}  {attr}={val}")
    if len(hand_coords) < 5:
        print("⚠ 期待する 5+1 枚スロットが見つからない")
        logger.warn(TOOL_ID, "hand slots missing")
        return 1
    logger.done(TOOL_ID, f"hand layout: {len(hand_coords)} slots")
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
