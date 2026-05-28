"""comm-discord-reply-guard — Discord 返信前のガード判定.

`feedback_discord_auto_reply` 準拠で「不利情報 10 カテゴリ」を含まないかチェック。
ヒットしたら blockingly warn、ヒットしなければ auto-reply 自走 OK のシグナル。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "comm-discord-reply-guard"

UNFAVORABLE = {
    "internal_finance": r"売上|収益|赤字|黒字|月商|年商|ARR|MRR",
    "internal_health": r"診断|処方|睡眠|うつ|不安|頭痛|症状",
    "private_relationship": r"はるか|元カノ|別れ|喧嘩",
    "credentials": r"sk_(?:live|test)_|whsec_|api[_-]?key|password",
    "private_paths": r"/Users/emocute/",
    "claude_chat": r"claude[\s_-]?arata|claude[\s_-]?chat",
    "shadow_session": r"影セッション|kasouba|silencer",
    "future_release": r"次のアルバム|未発表|準備中",
    "absolute_dates": r"\b20\d\d-\d\d-\d\d\b",
    "internal_codenames": r"溶けて|keep it|肺MV",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute comm discord-reply-guard")
    p.add_argument("text_file", nargs="?")
    return p


def run(args: argparse.Namespace) -> int:
    if args.text_file:
        text = Path(args.text_file).read_text()
    else:
        text = sys.stdin.read()
    hits = []
    for cat, pat in UNFAVORABLE.items():
        if re.search(pat, text, flags=re.IGNORECASE):
            hits.append(cat)
    if hits:
        print("⚠ unfavorable categories detected:")
        for h in hits:
            print(f"  • {h}")
        logger.warn(TOOL_ID, f"guard hit: {hits}")
        return 1
    print("✅ safe to auto-reply")
    logger.done(TOOL_ID, "guard passed")
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
