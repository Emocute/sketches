"""sale-dsp-reach-check — DSP の販売国カバレッジを確認.

各 DSP (Spotify/Apple/YouTube Music) で「該当国で配信されているか」を
販売物 ISRC ベースで突き合わせる plan を出す。実 API は songwhip / odesli を想定。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-dsp-reach-check"

EXPECTED_DSPS = ["spotify", "appleMusic", "youtube", "deezer", "tidal", "amazonMusic"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale dsp-reach-check")
    p.add_argument("releases_json", help="{title: [isrc, ...]} の JSON")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    p = Path(args.releases_json).expanduser().resolve()
    if not p.exists():
        logger.error(TOOL_ID, f"not found: {p}")
        return 2
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        logger.error(TOOL_ID, f"invalid json: {e}")
        return 2
    plan = []
    for title, isrcs in data.items():
        for isrc in isrcs:
            plan.append({
                "title": title,
                "isrc": isrc,
                "query": f"https://song.link/i/{isrc}",
                "expected_dsps": EXPECTED_DSPS,
            })
    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print(f"checks: {len(plan)}")
        for x in plan:
            print(f"  {x['title'][:30]:<30s}  {x['isrc']}  → {x['query']}")
        print(f"\n⚠ 実検証は song.link/odesli 経由。本ツールは plan のみ")
    logger.done(TOOL_ID, f"dsp reach plan: {len(plan)}")
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
