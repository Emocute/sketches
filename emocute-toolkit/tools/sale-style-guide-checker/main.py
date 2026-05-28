"""sale-style-guide-checker — 販売物の身内ラフ表現スキャン.

`feedback_no_unsolicited_marketing_copy` + Downloads/CLAUDE.md § 販売物の文書
準拠で「いい感じのやつ」「ヤバい」「出来合いの」等を販売物 LP/カタログ/
商品説明から grep。`feedback_writing_register_elevation` の対象。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-style-guide-checker"

# 身内ラフ表現 + 過度な煽り
PATTERNS = {
    "rough_register": r"いい感じ|ヤバ[いー]|エモい|ガチで|出来合いの|目玉(パーツ|テンプレ)|素材となる",
    "hype_overreach": r"業界を破壊|世界を変え|革命|圧倒的に|想像を超え|前代未聞|衝撃の",
    "internal_codename": r"溶けて|keep it|肺MV|内部MV-",
    "casual_jp": r"〜的な|っぽい|的な感じ|みたいな|まじで|だよね",
    "marketing_cliche": r"今だけ|限定価格|早い者勝ち|お早めに|逃すと損",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale style-guide-checker")
    p.add_argument("path", help="file or directory")
    p.add_argument("--ext", default="md,html,txt,json,vue")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    exts = {f".{e}" for e in args.ext.split(",")}
    files = [root] if root.is_file() else [
        f for f in root.rglob("*")
        if f.is_file() and f.suffix in exts and "_archive" not in f.parts and ".git" not in f.parts
    ]
    hits: list[tuple[Path, str, str]] = []
    for f in files:
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        # base64 埋込 HTML は誤マッチするので除外
        clean = re.sub(r"data:[^;]+;base64,[A-Za-z0-9+/=]+", "", text)
        for cat, pat in PATTERNS.items():
            for m in re.finditer(pat, clean):
                hits.append((f, cat, m.group(0)))
    print(f"scanned: {len(files)} files")
    if not hits:
        print("✅ no style violations found")
        logger.done(TOOL_ID, "style ok")
        return 0
    print(f"⚠ {len(hits)} hits:")
    for f, cat, frag in hits[:30]:
        rel = f.relative_to(root) if root.is_dir() else f.name
        print(f"  {cat:<20} '{frag[:30]}'  {rel}")
    logger.warn(TOOL_ID, f"style violations: {len(hits)}")
    return 1


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
