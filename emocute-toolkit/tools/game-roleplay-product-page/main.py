"""game-roleplay-product-page — Kagebu 商品ページ HTML 生成.

人格カタログ md → 商品紹介 HTML。`feedback_no_unsolicited_marketing_copy`
準拠で売り文句は埋めず、機能リスト・価格・ライセンス・OS 動作環境のみ。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-roleplay-product-page"

HTML_TPL = """<!doctype html>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{ background:#0a0a0a; color:#eee; font-family:sans-serif; max-width:720px; margin:40px auto; padding:0 20px; }}
h1 {{ font-size:1.8em; }}
table {{ width:100%; border-collapse:collapse; }}
td, th {{ border-bottom:1px solid #333; padding:8px; text-align:left; }}
</style>
<h1>{title}</h1>
<p>{description}</p>
<table>
<tr><th>項目</th><th>内容</th></tr>
<tr><td>価格</td><td>¥{price_jpy} (税込)</td></tr>
<tr><td>収録人格数</td><td>{persona_count}</td></tr>
<tr><td>配布形式</td><td>ZIP (md + 補足資料)</td></tr>
<tr><td>動作環境</td><td>Apple Notes / Obsidian / Anytype 等</td></tr>
<tr><td>ライセンス</td><td>商用利用不可・買い切り・個人利用</td></tr>
<tr><td>販売事業者</td><td>Emocute Lab.</td></tr>
<tr><td>連絡先</td><td>support@emocutelab.com</td></tr>
</table>
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game roleplay-product-page")
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--price-jpy", type=int, required=True)
    p.add_argument("--persona-count", type=int, required=True)
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    html = HTML_TPL.format(
        title=args.title,
        description=args.description or "(売り文句は空。機能と価格のみ)",
        price_jpy=args.price_jpy,
        persona_count=args.persona_count,
    )
    print(f"product: {args.title}  ¥{args.price_jpy}  ({args.persona_count} personas)")
    if not args.apply:
        print(html[:500])
        print("\n[dry-run]")
        return 0
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"page {args.title}")
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
