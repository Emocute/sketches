"""sale-en-native-score — 販売物 EN テキストの「機械翻訳臭」スコア.

`sale_en_native_required` 準拠。機械翻訳の特徴 (副詞重複/冠詞欠落/
直訳カタカナ綴り/句読点全角混入) をパターン検出してスコア化。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-en-native-score"

# 機械翻訳でよくある違和感パターン
PATTERNS = [
    (r"[、。「」『』（）]", "全角句読点が EN に混入"),
    (r"\b(this|the) (this|the) \b", "冠詞重複"),
    (r"\b(very|so) (very|so) \b", "副詞重複"),
    (r"\b(can|could) be able to\b", "二重助動詞"),
    (r"\bplease please\b", "please 重複"),
    (r"\bI think that I think\b", "従属節重複"),
    (r"\bdo a (work|listen|play)\b", "do + 名詞 不自然"),
    (r"  +", "連続スペース"),
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale en-native-score")
    p.add_argument("input")
    p.add_argument("--threshold", type=int, default=3, help="この件数超で fail")
    return p


def run(args: argparse.Namespace) -> int:
    p = Path(args.input).expanduser().resolve()
    if not p.exists():
        logger.error(TOOL_ID, f"not found: {p}")
        return 2
    text = p.read_text(errors="ignore")
    hits = []
    for pat, label in PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            ctx_start = max(0, m.start() - 20)
            ctx = text[ctx_start:m.end() + 20].replace("\n", " ")
            hits.append({"label": label, "match": m.group(), "context": ctx})
    print(f"file: {p.name}")
    print(f"hits: {len(hits)}  (threshold: {args.threshold})")
    for h in hits[:30]:
        print(f"  ⚠ [{h['label']}]  '{h['match']}'")
        print(f"      …{h['context']}…")
    if len(hits) > args.threshold:
        print(f"\n⚠ score {len(hits)} > threshold {args.threshold} → 機械翻訳臭あり。ネイティブ rewrite 推奨")
    logger.done(TOOL_ID, f"score {len(hits)}")
    return 0 if len(hits) <= args.threshold else 1


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
