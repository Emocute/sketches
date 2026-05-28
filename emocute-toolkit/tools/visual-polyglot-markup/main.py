"""visual-polyglot-markup — 多言語字幕の HTML/SVG 出力.

歌詞ファイル (JP/EN) を 1 行ずつ並列に配置した SVG/HTML を生成。
Visual の歌詞オーバーレイ用。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-polyglot-markup"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual polyglot-markup")
    p.add_argument("jp")
    p.add_argument("en")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--format", choices=["html", "svg"], default="html")
    p.add_argument("--apply", action="store_true")
    return p


HTML_TPL = """<!doctype html>
<meta charset="utf-8">
<style>
body {{ background:#000; color:#fff; font:32px/1.6 sans-serif; padding:40px; }}
.row {{ margin-bottom:1.5em; }}
.jp {{ font-size:1.2em; }}
.en {{ opacity:0.6; font-style:italic; }}
</style>
{body}
"""


def run(args: argparse.Namespace) -> int:
    jp = Path(args.jp).expanduser().resolve()
    en = Path(args.en).expanduser().resolve()
    if not jp.exists() or not en.exists():
        logger.error(TOOL_ID, "input files missing")
        return 2
    jl = jp.read_text().splitlines()
    el = en.read_text().splitlines()
    pairs = list(zip(jl, el))
    extra_jp = jl[len(pairs):]
    extra_en = el[len(pairs):]
    if extra_jp or extra_en:
        logger.warn(TOOL_ID, f"line count mismatch: jp={len(jl)} en={len(el)}")
    out = Path(args.out).expanduser().resolve()
    print(f"pairs: {len(pairs)}  jp_extra: {len(extra_jp)}  en_extra: {len(extra_en)}")
    if not args.apply:
        print("[dry-run]")
        return 0
    if args.format == "html":
        body = "\n".join(
            f'<div class="row"><div class="jp">{j}</div><div class="en">{e}</div></div>'
            for j, e in pairs)
        content = HTML_TPL.format(body=body)
    else:
        rows = []
        for i, (j, e) in enumerate(pairs):
            y1 = 40 + i*60
            y2 = y1 + 24
            rows.append(f'<text x="20" y="{y1}" font-size="22" fill="#fff">{j}</text>')
            rows.append(f'<text x="20" y="{y2}" font-size="14" fill="#aaa" font-style="italic">{e}</text>')
        content = f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="{40+len(pairs)*60}">{"".join(rows)}</svg>'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content)
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"polyglot {args.format} -> {out.name}")
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
