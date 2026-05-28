"""ops-session-handoff-md — セッション引継 md 生成.

`<PJ>/_drafts/handoff_<date>.md` を雛形付きで作成 (claude-chat 禁止運用、
md ファイルで引継ぐ `feedback_claude_to_claude_dialogue` 準拠)。
"""
from __future__ import annotations
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-session-handoff-md"

TPL = """# Handoff — {pj} ({date})

## 何をやってた
- (1-3 行)

## 何が未完
- (1-3 行)

## 次の打席が触るもの
- ファイル:
- コマンド:
- 注意:

## 関連メモリ/PR/issue
-
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops session-handoff-md")
    p.add_argument("pj_root")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.pj_root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    drafts = root / "_drafts"
    out = drafts / f"handoff_{date.today().isoformat()}.md"
    body = TPL.format(pj=root.name, date=date.today().isoformat())
    print(f"out: {out}")
    if not args.apply:
        print(body)
        print("[dry-run]")
        return 0
    drafts.mkdir(parents=True, exist_ok=True)
    if out.exists():
        logger.warn(TOOL_ID, f"already exists: {out}")
        return 1
    out.write_text(body)
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"handoff md for {root.name}")
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
