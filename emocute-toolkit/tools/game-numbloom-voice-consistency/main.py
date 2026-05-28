"""game-numbloom-voice-consistency — 25 人格の voice (口調) 一貫性チェック.

各 persona の台詞集を読み込んで「敬語使用率」「タメ口率」を計測。
人格ごとに期待プロファイルと一致しているか。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-numbloom-voice-consistency"

KEIGO_ENDINGS = ["です", "ます", "ません", "ですか", "ましょう"]
TAMEGUCHI_ENDINGS = ["だ", "だよ", "だね", "じゃん", "かよ", "なの", "?", "！"]


def measure(lines: list[str]) -> dict:
    n = max(1, len(lines))
    k = sum(1 for l in lines if any(l.rstrip().endswith(e) for e in KEIGO_ENDINGS))
    t = sum(1 for l in lines if any(l.rstrip().endswith(e) for e in TAMEGUCHI_ENDINGS))
    return {"n": n, "keigo_pct": round(k/n*100, 1), "tameguchi_pct": round(t/n*100, 1)}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game numbloom-voice-consistency")
    p.add_argument("persona_dir", help="各 persona の dialogues.txt 集積")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.persona_dir).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    results = {}
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        txt = d / "dialogues.txt"
        if not txt.exists():
            continue
        lines = [l.strip() for l in txt.read_text(errors="ignore").splitlines() if l.strip()]
        results[d.name] = measure(lines)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"{'persona':<20} {'n':>4} {'keigo%':>7} {'tame%':>6}")
        print("-" * 50)
        for name, r in results.items():
            print(f"{name:<20} {r['n']:>4} {r['keigo_pct']:>7} {r['tameguchi_pct']:>6}")
    logger.done(TOOL_ID, f"voice: {len(results)} personas")
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
