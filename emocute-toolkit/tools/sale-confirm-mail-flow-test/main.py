"""sale-confirm-mail-flow-test — 購入確認メールのフロー E2E テスト計画.

Stripe webhook → Resend send → ユーザ受信、までの全段の通過テスト計画。
本ツールは plan + チェック項目のみ (実 E2E は playwright + mailtrap想定)。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-confirm-mail-flow-test"

CHECKLIST = [
    "Stripe test mode payment intent succeeded",
    "Site /api/stripe-webhook 200 で reply",
    "Supabase orders に row 追加",
    "Resend send queue に enqueue",
    "Resend logs で delivered 確認",
    "mailtrap inbox に到達",
    "ダウンロードリンク有効 + 期限内",
    "JP/EN テンプレが選択 (顧客 locale で)",
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale confirm-mail-flow-test")
    p.add_argument("--scenario", choices=["jp_card", "us_card", "refund"], default="jp_card")
    return p


def run(args: argparse.Namespace) -> int:
    print(f"scenario: {args.scenario}")
    print("checklist:")
    for i, c in enumerate(CHECKLIST, 1):
        print(f"  [ ] {i}. {c}")
    print("\n⚠ 実行は手動 + playwright。本ツールはチェックリスト提示のみ")
    logger.done(TOOL_ID, f"plan: {args.scenario}")
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
