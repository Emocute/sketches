"""sale-spotify-playlist-pitch — Spotify for Artists プレイリスト pitch 文面生成.

新曲リリース時のメタ (genre, mood, instrument, themes) から 500 字以内の
pitch 本文を生成。tone は控えめ (`writing_register_elevation` 準拠)。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-spotify-playlist-pitch"

LIMIT = 500


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale spotify-playlist-pitch")
    p.add_argument("--title", required=True)
    p.add_argument("--genres", nargs="+", required=True)
    p.add_argument("--moods", nargs="+", required=True)
    p.add_argument("--instruments", nargs="+", default=[])
    p.add_argument("--description", default="")
    return p


def run(args: argparse.Namespace) -> int:
    parts = [
        f'"{args.title}" is a {", ".join(args.moods)} track in the {", ".join(args.genres)} space.',
    ]
    if args.instruments:
        parts.append(f"Built around {', '.join(args.instruments)}.")
    if args.description:
        parts.append(args.description.strip())
    parts.append(
        "Emocute is a Tokyo-based solo project releasing exclusively as an independent artist."
    )
    body = " ".join(parts)
    n = len(body)
    print(body)
    print(f"\n--- {n}/{LIMIT} chars ", end="")
    print("⚠ OVER" if n > LIMIT else "OK", "---")
    logger.done(TOOL_ID, f"pitch {n} chars")
    return 0 if n <= LIMIT else 1


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
