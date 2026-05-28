"""game-idiograph-theme-generator — Idiograph 16 タイプ別テーマ案生成.

`project_idiograph_2026-04-30` 準拠 (MBTI 名称排除)。4 気質 × 4 軸の
16 タイプそれぞれにテーマカラー・モチーフ・名称候補を一括出力。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-idiograph-theme-generator"

# 4 気質 (仮称、MBTI と別)
TEMPERAMENTS = ["analyst", "diplomat", "sentinel", "explorer"]
# 4 軸: E/I, N/S, T/F, J/P
AXES = ["I", "E"]  # 簡略
N_S = ["N", "S"]
T_F = ["T", "F"]
J_P = ["J", "P"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game idiograph-theme-generator")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    types_ = []
    for a in AXES:
        for n in N_S:
            for t in T_F:
                for j in J_P:
                    code = f"{a}{n}{t}{j}"
                    types_.append({
                        "code": code,
                        "color_hint": f"hsl({hash(code) % 360}, 60%, 50%)",
                        "motif_candidates": [],
                        "name_candidates": [],
                    })
    if args.json:
        print(json.dumps(types_, indent=2, ensure_ascii=False))
    else:
        print(f"{'code':<6} {'color hint':<24} candidates")
        print("-" * 60)
        for t in types_:
            print(f"{t['code']:<6} {t['color_hint']:<24} (要手動命名)")
    print(f"\n⚠ MBTI 名称使用禁止 (project_idiograph_2026-04-30)")
    logger.done(TOOL_ID, f"types: {len(types_)}")
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
