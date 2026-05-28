"""research-llm-eval-archive — 外部 LLM 評価結果アーカイブ.

`<PJ>/_export/<pj>_eval_minimal.md` を `_archive/llm_evals/<date>/` に複製、
過去評価との比較用に時系列保存。
"""
from __future__ import annotations
import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "research-llm-eval-archive"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute research llm-eval-archive")
    p.add_argument("eval_md")
    p.add_argument("--archive-root", default="~/Downloads/_archive/llm_evals")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.eval_md).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    archive_root = Path(args.archive_root).expanduser().resolve()
    dest = archive_root / date.today().isoformat() / src.name
    print(f"src:  {src}")
    print(f"dest: {dest}")
    if not args.apply:
        print("[dry-run]")
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        logger.warn(TOOL_ID, f"already archived today: {dest}")
        return 1
    shutil.copy(src, dest)
    print(f"✅ archived → {dest}")
    logger.done(TOOL_ID, f"eval archived: {src.name}")
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
