"""game-numbloom-poc-validate — Numbloom POC HTML の整合性検査.

`game.html` 単一ファイル PJ。PixiJS 読み込み・SVG 枝配置 (`menu_sacred`)・
絵文字混入禁止 (`combat_visual`) 等の規約を grep ベースで検査。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-numbloom-poc-validate"

# 規約検査
RULES = [
    {"name": "pixijs_loaded", "pattern": r"pixi(\.min)?\.js", "must": True,
     "violation": "PixiJS 必須 (project_numbloom_identity_2026-03-24)"},
    {"name": "no_emoji", "pattern": r"[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF]", "must": False,
     "violation": "絵文字禁止 (feedback_combat_visual_direction)"},
    {"name": "menu_sacred", "pattern": r"<svg[^>]*menu", "must": True,
     "violation": "SVG メニュー枝必須 (feedback_menu_sacred)"},
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game numbloom-poc-validate")
    p.add_argument("game_html")
    return p


def run(args: argparse.Namespace) -> int:
    p = Path(args.game_html).expanduser().resolve()
    if not p.exists():
        logger.error(TOOL_ID, f"not found: {p}")
        return 2
    text = p.read_text(errors="ignore")
    fail = 0
    print(f"file: {p.name}")
    for r in RULES:
        found = bool(re.search(r["pattern"], text))
        ok = found == r["must"]
        mark = "✅" if ok else "⚠"
        print(f"  {mark} {r['name']:<22s}  {'OK' if ok else r['violation']}")
        if not ok:
            fail += 1
    logger.done(TOOL_ID, f"numbloom validate fail={fail}")
    return 0 if fail == 0 else 1


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
