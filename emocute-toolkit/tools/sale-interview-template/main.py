"""sale-interview-template — 取材回答テンプレ初稿生成.

`interview_draft_no_average` 準拠で「AI 平均化臭」を避けるよう、
Q ごとに「究の生アイデア起点」を必須フィールドにしてスケルトンを出す。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-interview-template"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale interview-template")
    p.add_argument("questions_file", help="1 行 1 質問")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.questions_file).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    qs = [l.strip() for l in src.read_text().splitlines() if l.strip() and not l.startswith("#")]
    print(f"questions: {len(qs)}")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    md_parts = ["# 取材回答ドラフト\n",
                "**注意**: `interview_draft_no_average` 準拠。各 Q の `raw_idea_by_kiku` を必ず究が手書き埋め。Claude は出力エディトのみ。\n"]
    for i, q in enumerate(qs, 1):
        md_parts.append(f"\n## Q{i}. {q}\n")
        md_parts.append(f"- `raw_idea_by_kiku`: \n- `polished_answer`: (空、究の raw_idea を整える役)\n")
    out.write_text("\n".join(md_parts))
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"template {len(qs)} qs")
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
