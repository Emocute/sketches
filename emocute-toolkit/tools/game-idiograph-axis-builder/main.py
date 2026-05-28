"""game-idiograph-axis-builder — Idiograph の I/E, J/P 軸設問設計.

各軸 (I/E, N/S, T/F, J/P) について 5 問程度の YES/NO 質問テンプレを生成。
MBTI 由来の質問文をそのまま使うとライセンス問題なので、独自設計の足がかり。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-idiograph-axis-builder"

# 各軸のテーマ枠 (独自質問の出発点としての contrasting attribute)
AXIS_FRAMES = {
    "I/E": [("内省で消耗を回復する", "対人接触で消耗を回復する"),
            ("先に考える", "話しながら考える"),
            ("少人数を好む", "大人数を好む")],
    "N/S": [("抽象や類推で理解", "具体や事実で理解"),
            ("将来像から逆算", "現在の状況から積み上げ"),
            ("可能性を見る", "実際を見る")],
    "T/F": [("一貫性を重視", "影響を重視"),
            ("論理で説得", "共感で説得"),
            ("批判は機能", "批判は侵害")],
    "J/P": [("締切を先に立てる", "締切は最後に決める"),
            ("計画通りに動く", "状況に応じて動く"),
            ("結論を急ぐ", "情報を集め続ける")],
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game idiograph-axis-builder")
    p.add_argument("--axis", choices=list(AXIS_FRAMES.keys()))
    return p


def run(args: argparse.Namespace) -> int:
    axes = [args.axis] if args.axis else list(AXIS_FRAMES.keys())
    for a in axes:
        print(f"\n=== axis: {a} ===")
        for i, (a_side, b_side) in enumerate(AXIS_FRAMES[a], 1):
            print(f"  Q{i}. {a_side}  vs.  {b_side}")
        print(f"  ⚠ MBTI 由来の質問文を引用せず、独自に rephrase")
    logger.done(TOOL_ID, f"axis frames: {len(axes)}")
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
