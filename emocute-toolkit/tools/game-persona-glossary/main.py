"""game-persona-glossary — Kagebu/Numbloom 人格用語集生成.

`personas_master/` 内の md からロール名・特殊用語を抽出して用語集 md を出力。
"""
from __future__ import annotations
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-persona-glossary"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game persona-glossary")
    p.add_argument("personas_root")
    p.add_argument("-o", "--out", default="-")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.personas_root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    terms: Counter[str] = Counter()
    for f in root.rglob("*.md"):
        text = f.read_text(errors="ignore")
        for m in re.findall(r"\b([A-Z]{2,4})\b", text):
            terms[m] += 1
    print(f"unique tokens: {len(terms)}")
    out_lines = ["# 人格用語集", ""]
    for term, n in terms.most_common(40):
        out_lines.append(f"- **{term}** — 出現 {n} 回")
    body = "\n".join(out_lines)
    if args.out == "-":
        print(body[:400])
        print("...")
    else:
        Path(args.out).write_text(body)
        print(f"✅ wrote {args.out}")
    logger.done(TOOL_ID, f"glossary terms: {len(terms)}")
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
