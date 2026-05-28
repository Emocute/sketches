"""game-kagebu-role-prefix-gen — Kagebu 人格用 2 文字ロールプレフィックス生成.

既存 12 体（XO/HR/ND/BD/MP/DE/NT/HB/YB/MX/PS/MT）と衝突しない
2 文字大文字英字コードを候補列挙。
"""
from __future__ import annotations
import argparse
import itertools
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-kagebu-role-prefix-gen"

EXISTING = {"XO", "HR", "ND", "BD", "MP", "DE", "NT", "HB", "YB", "MX", "PS", "MT"}
# よくある typo / 一般略語と被るもの
RESERVED = {"OK", "NG", "AI", "ML", "JP", "EN", "UI", "UX", "PC", "SF", "FB", "TW",
            "HQ", "FR", "DE", "PR", "QA", "OS", "IP", "TV", "PV", "MV", "AV", "OP",
            "EX", "VS", "AM", "PM"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game kagebu-role-prefix-gen")
    p.add_argument("-n", type=int, default=20, help="生成数")
    p.add_argument("--seed", type=int)
    p.add_argument("--hint", default="", help="A-Z 含めて欲しい文字")
    return p


def run(args: argparse.Namespace) -> int:
    if args.seed is not None:
        random.seed(args.seed)
    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    pairs = list(itertools.permutations(letters, 2))
    pool = ["".join(p) for p in pairs
            if "".join(p) not in EXISTING and "".join(p) not in RESERVED]
    if args.hint:
        h = args.hint.upper()
        pool = [p for p in pool if any(c in p for c in h)]
    random.shuffle(pool)
    out = pool[:args.n]
    print(f"{len(out)} candidates:")
    for c in out:
        print(f"  {c}")
    logger.done(TOOL_ID, f"{len(out)} prefixes")
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
