"""sale-post-replicator — X 過去ポストの再ポスト計画.

`reference_x_scrape_script` で抜いたポスト JSONL からエンゲージメント
上位 N 件を抽出、リサイクル候補として再投稿スケジュール案を出力。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-post-replicator"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale post-replicator")
    p.add_argument("posts_jsonl")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--min-likes", type=int, default=20)
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    p = Path(args.posts_jsonl).expanduser().resolve()
    if not p.exists():
        logger.error(TOOL_ID, f"not found: {p}")
        return 2
    posts = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            posts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    qualified = [x for x in posts if x.get("likes", 0) >= args.min_likes]
    qualified.sort(key=lambda x: -x.get("likes", 0))
    top = qualified[:args.top]
    if args.json:
        print(json.dumps(top, ensure_ascii=False, indent=2))
    else:
        print(f"qualified: {len(qualified)} / total {len(posts)}")
        print(f"top {args.top}:")
        for i, post in enumerate(top, 1):
            text = post.get("text", "")[:80]
            print(f"  {i:2d}  likes={post.get('likes',0):>5}  {text}")
    logger.done(TOOL_ID, f"replicator top={len(top)}")
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
