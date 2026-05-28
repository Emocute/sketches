"""research-pain-extract — memory/feedback 内 pain point 抽出.

「禁止」「いらない」「やめて」「だめ」「stop」「don't」「うざい」等のキー
ワードと前後文脈を抽出して、頻出 pain point を集計。
"""
from __future__ import annotations
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "research-pain-extract"

PAIN_RE = re.compile(r"(禁止|いらない|やめて|だめ|stop|don[' ]?t|うざい|嫌い|怒|無理)", re.IGNORECASE)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute research pain-extract")
    p.add_argument("memory_root")
    p.add_argument("--limit", type=int, default=20)
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.memory_root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    pains: list[tuple[Path, str]] = []
    for f in root.glob("*.md"):
        for line in f.read_text(errors="ignore").splitlines():
            if PAIN_RE.search(line):
                pains.append((f, line.strip()))
    counter = Counter(p[0].stem for p in pains)
    print(f"pain occurrences: {len(pains)}")
    print(f"\ntop memory files by pain count:")
    for stem, n in counter.most_common(args.limit):
        print(f"  {n:>4}  {stem}")
    logger.done(TOOL_ID, f"pain: {len(pains)}")
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
