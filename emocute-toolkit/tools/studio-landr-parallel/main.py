"""studio-landr-parallel — LANDR 並列マスタリング投入計画.

複数トラックを LANDR Studio Pro で並列マスタリング。プリセット
(Warm-High / Balanced-Medium / Open-Medium 等) を組み合わせて A/B 比較。

実 LANDR 操作は Playwright/MCP 経由なので本ツールは plan 出力のみ。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-landr-parallel"

PRESETS = ["Warm-High", "Balanced-Medium", "Open-Medium", "Warm-Medium"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio landr-parallel")
    p.add_argument("tracks", nargs="+", help="トラックファイル群")
    p.add_argument("--presets", nargs="+", default=["Warm-High"])
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    invalid = [t for t in args.tracks if not Path(t).expanduser().exists()]
    if invalid:
        logger.error(TOOL_ID, f"missing: {invalid}")
        return 2
    bad = [p for p in args.presets if p not in PRESETS]
    if bad:
        logger.error(TOOL_ID, f"unknown preset: {bad}. allowed={PRESETS}")
        return 2
    jobs = []
    for t in args.tracks:
        for p in args.presets:
            jobs.append({"track": Path(t).name, "preset": p})
    if args.json:
        print(json.dumps(jobs, ensure_ascii=False, indent=2))
    else:
        print(f"jobs: {len(jobs)}  ({len(args.tracks)} tracks × {len(args.presets)} presets)")
        for j in jobs:
            print(f"  - {j['track']}  →  {j['preset']}")
        print("\n⚠ LANDR Studio Pro 1ヶ月契約必須 (landr_batch_remaster_plan 参照)")
    logger.done(TOOL_ID, f"plan {len(jobs)} jobs")
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
