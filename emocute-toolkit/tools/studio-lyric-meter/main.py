"""studio-lyric-meter — 歌詞 (JP) の音節カウントとリズム解析.

ひらがな・カタカナ・漢字を含む行の音節数を概算。
Suno に渡す前にラインごとの整合性確認。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-lyric-meter"

# 音節としてカウントしないもの（拗音・促音）
SUB_KANA = "ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ"
PUNCT_RE = re.compile(r"[、。「」『』（）\[\]\.\,\s]")
KANA_RE = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")
KANJI_RE = re.compile(r"[\u4E00-\u9FFF]")


def count_syllables(line: str) -> int:
    """JP 音節を概算。漢字は 2 音節とみなす（妥協）"""
    text = PUNCT_RE.sub("", line)
    syl = 0
    for ch in text:
        if ch in SUB_KANA:
            continue
        if KANA_RE.match(ch):
            syl += 1
        elif KANJI_RE.match(ch):
            syl += 2
        elif ch.isalnum():
            syl += 0.5  # ローマ字・数字は半音節相当
    return int(round(syl))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio lyric-meter")
    p.add_argument("input", help="歌詞テキストファイル")
    p.add_argument("--target", type=int, help="期待する音節数 (省略可)")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    text = inp.read_text(errors="ignore")
    lines = [l.strip() for l in text.splitlines()]
    rows = []
    for i, line in enumerate(lines, 1):
        if not line:
            continue
        c = count_syllables(line)
        rows.append({"line": i, "text": line, "syllables": c})

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(f"{'line':<5} {'syll':<5} text")
        print("-" * 70)
        for r in rows:
            warn = ""
            if args.target and abs(r["syllables"] - args.target) > 2:
                warn = " ⚠"
            print(f"{r['line']:<5} {r['syllables']:<5} {r['text'][:50]}{warn}")
        if args.target:
            within = sum(1 for r in rows if abs(r["syllables"] - args.target) <= 2)
            print(f"\nwithin ±2 of target ({args.target}): {within}/{len(rows)}")
    logger.done(TOOL_ID, f"meter: {len(rows)} lines")
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
