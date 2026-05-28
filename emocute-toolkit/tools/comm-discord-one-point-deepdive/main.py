"""comm-discord-one-point-deepdive — Discord ブレスト形式チェック.

`feedback_discord_brainstorm_pace` 準拠で ABCDE 列挙ドラフトを警告し、
1 点に絞った深掘り構造 (主張 → 先行事例 → 反証 → 結論) を強制する linter。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "comm-discord-one-point-deepdive"

ENUM_RE = re.compile(r"^\s*[A-E][\.\)]\s", re.MULTILINE)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute comm discord-one-point-deepdive")
    p.add_argument("text_file", nargs="?")
    return p


def run(args: argparse.Namespace) -> int:
    if args.text_file:
        text = Path(args.text_file).read_text()
    else:
        text = sys.stdin.read()
    enum_hits = ENUM_RE.findall(text)
    if len(enum_hits) >= 3:
        print(f"⚠ ABCDE 列挙検出 ({len(enum_hits)} 件)。1 点に絞り直せ")
        logger.warn(TOOL_ID, f"enum drift: {len(enum_hits)}")
        return 1
    print("✅ 列挙形式に陥っていない")
    logger.done(TOOL_ID, "deepdive shape ok")
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
