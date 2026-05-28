"""ops-pj-start-unified — PJ 起動時の統一チェック.

PJ ルートで起動 → CLAUDE.md / TODO.md / 直近 SESSION_LOG.md の末尾 + 未完項目を
1 画面に纏める (`feedback_session_start_no_recap` 準拠で recap は書かない、
未完と次やる作業のみ)。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-pj-start-unified"


def tail(path: Path, n: int = 20) -> str:
    if not path.exists():
        return f"(no {path.name})"
    lines = path.read_text(errors="ignore").splitlines()
    return "\n".join(lines[-n:])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops pj-start-unified")
    p.add_argument("pj_root")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.pj_root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    print(f"\n=== {root.name} ===")
    todo = root / "TODO.md"
    if todo.exists():
        print("\n--- TODO.md (未完 grep) ---")
        for line in todo.read_text(errors="ignore").splitlines():
            if "- [ ]" in line or "未完" in line or "🟡" in line or "⏳" in line:
                print(f"  {line}")
    session_log = root / "SESSION_LOG.md"
    print("\n--- SESSION_LOG.md tail 20 ---")
    print(tail(session_log, 20))
    print("\n[次やる作業のみ書け。recap 禁止 — feedback_session_start_no_recap]")
    logger.done(TOOL_ID, f"pj-start {root.name}")
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
