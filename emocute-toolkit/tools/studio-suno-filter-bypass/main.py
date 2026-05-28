"""studio-suno-filter-bypass — Suno のリリックフィルタ回避表記辞書.

`reference_suno_filter_workaround_2026-05-22` 準拠。よく弾かれるワードを
代替表記 (ローマ字混在・記号挿入・婉曲) に変換。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-suno-filter-bypass"

# 代替表記辞書 (リスト先頭ほど推奨)
SUBSTITUTIONS = {
    "kill":     ["k1ll", "ki!ll", "終わらせる"],
    "die":      ["d!e", "消える"],
    "blood":    ["bl00d", "深紅"],
    "bitch":    ["b!tch", "雌"],
    "drug":     ["dr*g", "薬"],
    "fuck":     ["f*ck", "壊す"],
    "shit":     ["sh!t", "屑"],
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio suno-filter-bypass")
    p.add_argument("input", help="歌詞ファイル or '-' で stdin")
    p.add_argument("--style", choices=["leet", "japanese", "list"], default="leet")
    p.add_argument("--json", action="store_true")
    return p


def transform(text: str, style: str) -> tuple[str, list[dict]]:
    out = text
    hits: list[dict] = []
    for word, subs in SUBSTITUTIONS.items():
        if word in out.lower():
            if style == "leet":
                replacement = subs[0]
            elif style == "japanese":
                replacement = subs[-1]
            else:
                replacement = f"<{word}>"
            # 大小文字保ったままざっくり置換 (簡易)
            import re
            n_before = len(out)
            out = re.sub(re.escape(word), replacement, out, flags=re.IGNORECASE)
            if n_before != len(out) or word.lower() in text.lower():
                hits.append({"word": word, "replacement": replacement})
    return out, hits


def run(args: argparse.Namespace) -> int:
    if args.input == "-":
        text = sys.stdin.read()
    else:
        path = Path(args.input).expanduser().resolve()
        if not path.exists():
            logger.error(TOOL_ID, f"not found: {path}")
            return 2
        text = path.read_text()
    if args.style == "list":
        if args.json:
            print(json.dumps(SUBSTITUTIONS, ensure_ascii=False, indent=2))
        else:
            for w, subs in SUBSTITUTIONS.items():
                print(f"  {w:<10s} → {', '.join(subs)}")
        return 0
    transformed, hits = transform(text, args.style)
    if args.json:
        print(json.dumps({"text": transformed, "hits": hits}, ensure_ascii=False, indent=2))
    else:
        print(transformed)
        if hits:
            print(f"\n--- substitutions ({len(hits)}) ---", file=sys.stderr)
            for h in hits:
                print(f"  {h['word']} → {h['replacement']}", file=sys.stderr)
    logger.done(TOOL_ID, f"bypass: {len(hits)} hits")
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
