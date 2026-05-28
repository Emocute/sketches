"""audit-style-guide — 販売物テキストのブランド/トーンチェック.

身内ラフ表現・小文字 emocute・煽り表現・絵文字過多を検出。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "audit-style-guide"

# 身内ラフ表現
ROUGH = ["いい感じ", "ヤバい", "ヤバ", "出来合い", "目玉テンプレ",
         "素材となる目玉", "やっとけ", "ガチ"]
# 小文字ブランド
LOWERCASE_BRAND = re.compile(r"\bemocute(?=\s+(が|は|の|を|に|で))")
# 攻撃的・煽り
AGGRESSIVE = ["業界を破壊", "終わらせる", "ぶっ壊す", "クソゲー", "ゴミ", "ザコ"]
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")

SCAN_EXTS = {".md", ".txt", ".html"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute audit style-guide")
    p.add_argument("path")
    p.add_argument("--emoji-limit", type=int, default=3, help="ファイル毎の絵文字許容上限")
    return p


def run(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    files = [target] if target.is_file() else [
        f for f in target.rglob("*")
        if f.is_file() and f.suffix.lower() in SCAN_EXTS
    ]
    hits: list[dict] = []
    for f in files:
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for term in ROUGH:
            for m in re.finditer(re.escape(term), text):
                line = text[:m.start()].count("\n") + 1
                hits.append({"file": f.name, "type": "rough", "value": term, "line": line})
        for m in LOWERCASE_BRAND.finditer(text):
            line = text[:m.start()].count("\n") + 1
            hits.append({"file": f.name, "type": "lowercase_brand", "value": m.group(0), "line": line})
        for term in AGGRESSIVE:
            for m in re.finditer(re.escape(term), text):
                line = text[:m.start()].count("\n") + 1
                hits.append({"file": f.name, "type": "aggressive", "value": term, "line": line})
        emoji_count = len(EMOJI_RE.findall(text))
        if emoji_count > args.emoji_limit:
            hits.append({"file": f.name, "type": "emoji_overflow",
                         "value": f"{emoji_count} emojis (limit {args.emoji_limit})", "line": 1})

    if hits:
        print(f"❌ {len(hits)} style issues")
        for h in hits[:40]:
            print(f"  [{h['type']}] {h['file'][:40]}:{h['line']}  '{h['value']}'")
        logger.warn(TOOL_ID, f"{len(hits)} style issues")
        return 1
    print(f"✅ style OK ({len(files)} files)")
    logger.done(TOOL_ID, f"clean: {len(files)} files")
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
