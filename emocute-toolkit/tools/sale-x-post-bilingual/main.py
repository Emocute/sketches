"""sale-x-post-bilingual — X 告知ポスト (JP+EN 混在) 生成.

`sale_x_post_jp_en_unified` 準拠で 1 ポストに JP + 改行 + EN を入れる。
販売リンク・サムネ画像パス・280字制限チェック付き。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-x-post-bilingual"

LIMIT = 280


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale x-post-bilingual")
    p.add_argument("--jp", required=True, help="日本語本文")
    p.add_argument("--en", required=True, help="英語本文")
    p.add_argument("--url", required=True)
    p.add_argument("--image", help="画像パス (添付)")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    body = f"{args.jp}\n\n{args.en}\n\n{args.url}"
    n = len(body)
    over = n - LIMIT
    if args.json:
        out = {"body": body, "chars": n, "over_limit": max(0, over),
               "image": args.image}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(body)
        print(f"\n--- chars: {n}/{LIMIT} ", end="")
        print("⚠ OVER" if over > 0 else "OK", "---")
        if args.image:
            print(f"image: {args.image}")
    logger.done(TOOL_ID, f"x-post {n} chars")
    return 0 if over <= 0 else 1


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
