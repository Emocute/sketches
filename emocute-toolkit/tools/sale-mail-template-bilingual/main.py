"""sale-mail-template-bilingual — JP/EN 同梱メールテンプレ生成.

問い合わせ・注文確認・再送・refund 通知などの定型を JP/EN 並列で出力。
`sale_en_native_required` 準拠でテンプレ自体はネイティブ品質前提。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-mail-template-bilingual"

TEMPLATES = {
    "order_confirm": {
        "jp": "ご購入ありがとうございます。\nダウンロードリンク: {download_url}\n— Emocute",
        "en": "Thank you for your purchase.\nDownload: {download_url}\n— Emocute",
    },
    "refund_done": {
        "jp": "返金処理が完了しました。お手数おかけしました。",
        "en": "Your refund has been processed. We apologize for the inconvenience.",
    },
    "resend_link": {
        "jp": "ダウンロードリンクを再発行しました: {download_url}\n有効期限: {expires}",
        "en": "Reissued download link: {download_url}\nExpires: {expires}",
    },
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale mail-template-bilingual")
    p.add_argument("template", choices=list(TEMPLATES.keys()))
    p.add_argument("--vars", nargs="*", default=[], help="key=value 形式")
    return p


def run(args: argparse.Namespace) -> int:
    tpl = TEMPLATES[args.template]
    kv = {}
    for s in args.vars:
        if "=" in s:
            k, _, v = s.partition("=")
            kv[k] = v
    try:
        jp = tpl["jp"].format(**{**{k: "{"+k+"}" for k in ["download_url","expires"]}, **kv})
        en = tpl["en"].format(**{**{k: "{"+k+"}" for k in ["download_url","expires"]}, **kv})
    except KeyError as e:
        logger.error(TOOL_ID, f"missing key: {e}")
        return 2
    print("=== JP ===")
    print(jp)
    print("\n=== EN ===")
    print(en)
    logger.done(TOOL_ID, f"template: {args.template}")
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
