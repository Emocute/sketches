"""studio-suno-prompt-tuner — Suno プロンプトの自動チューニング履歴.

過去 N 回の generation 結果 (rating / 採用 / 棄却) を Bayesian 風スコアで
集計、style 句ごとの「効いた / 効かなかった」順位を出す。
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-suno-prompt-tuner"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio suno-prompt-tuner")
    p.add_argument("log_jsonl", help="JSONL: {style_tokens:[..], rating:N, kept:bool}")
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    path = Path(args.log_jsonl).expanduser().resolve()
    if not path.exists():
        logger.error(TOOL_ID, f"not found: {path}")
        return 2
    scores: dict[str, list[int]] = defaultdict(list)
    kept: dict[str, int] = defaultdict(int)
    n_total = 0
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        toks = e.get("style_tokens") or []
        r = e.get("rating", 0)
        n_total += 1
        for t in toks:
            scores[t].append(r)
            if e.get("kept"):
                kept[t] += 1
    ranked = []
    for tok, rs in scores.items():
        avg = sum(rs) / len(rs)
        ranked.append({"token": tok, "n": len(rs), "avg_rating": round(avg, 2), "kept": kept[tok]})
    ranked.sort(key=lambda x: -x["avg_rating"])
    if args.json:
        print(json.dumps(ranked[:args.top], ensure_ascii=False, indent=2))
    else:
        print(f"sessions: {n_total}  unique tokens: {len(ranked)}")
        print(f"{'token':<28} {'n':>3} {'avg':>6} {'kept':>5}")
        print("-" * 60)
        for r in ranked[:args.top]:
            print(f"{r['token']:<28s} {r['n']:>3d} {r['avg_rating']:>6.2f} {r['kept']:>5d}")
    logger.done(TOOL_ID, f"tuner: {len(ranked)} tokens analyzed")
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
