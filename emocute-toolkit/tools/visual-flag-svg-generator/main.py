"""visual-flag-svg-generator — 国旗 SVG を長方形フラット生成.

memory: 国旗は長方形、circular/emoji 禁止。シンプル横ストライプのみ対応。
言語切替アイコン等に使う。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-flag-svg-generator"

# 横ストライプ国旗のみ（簡易）。記号付きはアセット直接添付推奨。
FLAGS = {
    "jp": [("white", 1)],  # 白地 + 中央赤円 (扱い別)
    "fr": [("#0055A4", 1), ("white", 1), ("#EF4135", 1)],  # 縦三色
    "de": [("black", 1), ("#DD0000", 1), ("#FFCE00", 1)],
    "ru": [("white", 1), ("#0039A6", 1), ("#D52B1E", 1)],
    "nl": [("#AE1C28", 1), ("white", 1), ("#21468B", 1)],
    "th": [("#A51931", 1), ("white", 1), ("#241D4F", 2), ("white", 1), ("#A51931", 1)],
    "us": [("#B22234", 1)] * 13,  # placeholder
    "kr": [("white", 1)],
}


def emit(flag: str, w: int, h: int) -> str:
    """簡易 SVG (3:2 比率)"""
    if flag == "jp":
        r = h * 0.6 / 2
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
                f'<rect width="{w}" height="{h}" fill="white"/>'
                f'<circle cx="{w/2}" cy="{h/2}" r="{r}" fill="#BC002D"/>'
                f'</svg>')
    if flag == "kr":
        # 簡易: 白地 + 中央太極（楕円代用）
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
                f'<rect width="{w}" height="{h}" fill="white"/>'
                f'<circle cx="{w/2}" cy="{h/2}" r="{h/3}" fill="#003478"/>'
                f'<path d="M {w/2-h/3},{h/2} a {h/6},{h/6} 0 0 1 {h/3},0 a {h/6},{h/6} 0 0 0 {h/3},0" fill="#C60C30"/>'
                f'</svg>')
    if flag == "fr":
        third = w / 3
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
                f'<rect x="0" y="0" width="{third}" height="{h}" fill="#0055A4"/>'
                f'<rect x="{third}" y="0" width="{third}" height="{h}" fill="white"/>'
                f'<rect x="{third*2}" y="0" width="{third}" height="{h}" fill="#EF4135"/>'
                f'</svg>')
    # generic horizontal stripes
    stripes = FLAGS.get(flag)
    if not stripes:
        return ""
    total = sum(w_ for _, w_ in stripes)
    y = 0
    parts = []
    for color, weight in stripes:
        sh = h * weight / total
        parts.append(f'<rect x="0" y="{y}" width="{w}" height="{sh}" fill="{color}"/>')
        y += sh
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
            + "".join(parts) + "</svg>")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual flag-svg-generator")
    p.add_argument("country", help=f"{list(FLAGS.keys())} or all")
    p.add_argument("-o", "--out-dir", required=True)
    p.add_argument("--width", type=int, default=30)
    p.add_argument("--height", type=int, default=20)
    return p


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    targets = list(FLAGS.keys()) if args.country == "all" else [args.country]
    bad = [t for t in targets if t not in FLAGS]
    if bad:
        logger.error(TOOL_ID, f"unknown: {bad}")
        return 2
    for c in targets:
        svg = emit(c, args.width, args.height)
        if not svg:
            print(f"  ⚠ {c} not supported")
            continue
        out = out_dir / f"flag_{c}.svg"
        out.write_text(svg)
        print(f"  ✅ {out.name}")
    logger.done(TOOL_ID, f"emit {len(targets)} flags")
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
