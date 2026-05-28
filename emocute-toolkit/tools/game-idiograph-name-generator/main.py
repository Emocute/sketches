"""game-idiograph-name-generator — MBTI 商標を踏まない 16 タイプ名候補生成.

形式: 2 語複合 + サフィックス。MBTI 由来語・16P 公式名を除外。
"""
from __future__ import annotations
import argparse
import itertools
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-idiograph-name-generator"

# MBTI / 16P 商標語（候補から除外）
BANNED_TERMS = {
    "architect", "logician", "commander", "debater", "advocate",
    "mediator", "protagonist", "campaigner", "logistician", "defender",
    "executive", "consul", "virtuoso", "adventurer", "entrepreneur", "entertainer",
    "thinker", "feeler", "judge", "perceiver", "intuitive", "sensor",
    "introvert", "extrovert", "extravert",
    "mbti", "16personalities", "16p",
}

CORES_JA = ["静観", "刻印", "潮", "陰影", "灯", "刃", "苔", "塵", "霞", "影", "舵",
            "灰", "蒸気", "鏡", "水脈", "結晶"]
CORES_EN = ["Tideborn", "Stillkeeper", "Inkbearer", "Mossworn", "Lanternheld",
            "Cinderpath", "Riftrunner", "Stonelung", "Glimmertongue", "Vaultsong",
            "Echoknot", "Saltcaller", "Frostgate", "Bonecaster", "Brinekeep", "Hollowveil"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game idiograph-name-generator")
    p.add_argument("--lang", choices=["ja", "en", "both"], default="both")
    p.add_argument("--seed", type=int)
    p.add_argument("--json", action="store_true")
    p.add_argument("-n", type=int, default=16, help="生成数")
    return p


def filter_safe(name: str) -> bool:
    low = name.lower()
    return not any(b in low for b in BANNED_TERMS)


def run(args: argparse.Namespace) -> int:
    if args.seed is not None:
        random.seed(args.seed)
    pool: list[str] = []
    if args.lang in {"en", "both"}:
        pool += [n for n in CORES_EN if filter_safe(n)]
    if args.lang in {"ja", "both"}:
        # JA は単独で十分短い、suffix で区別
        for c in CORES_JA:
            for suf in ["の灯", "の刻", "の場", "の路", "の門", "の鞘"]:
                cand = c + suf
                if filter_safe(cand):
                    pool.append(cand)
    random.shuffle(pool)
    out = pool[:args.n]
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"{len(out)} candidates (lang={args.lang})")
        for i, n in enumerate(out, 1):
            print(f"  [{i:>2}] {n}")
    logger.done(TOOL_ID, f"generated {len(out)} candidates")
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
