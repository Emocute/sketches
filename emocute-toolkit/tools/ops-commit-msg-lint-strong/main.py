"""ops-commit-msg-lint-strong — 強化版 commit-msg linter.

`Downloads/CLAUDE.md § コミットメッセージ` 準拠で type prefix・1 行目 72 字以下・
日本語推奨・Co-Authored-By 禁止 を検査。git hook と stdin 両方対応。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-commit-msg-lint-strong"

ALLOWED = {"feat", "fix", "perf", "refactor", "docs", "style", "test", "chore", "ci", "build"}
HEADER_RE = re.compile(r"^(\w+)(\([^)]+\))?: (.+)$")


def lint(msg: str) -> list[str]:
    errors: list[str] = []
    lines = msg.splitlines()
    if not lines:
        return ["empty message"]
    header = lines[0]
    if len(header) > 72:
        errors.append(f"header too long ({len(header)} > 72)")
    m = HEADER_RE.match(header)
    if not m:
        errors.append("header must be: type(scope?): description")
    elif m.group(1) not in ALLOWED:
        errors.append(f"unknown type: {m.group(1)} (allowed: {sorted(ALLOWED)})")
    if "Co-Authored-By" in msg or "Co-authored-by" in msg:
        errors.append("Co-Authored-By forbidden")
    return errors


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops commit-msg-lint-strong")
    p.add_argument("msg_file", nargs="?", default=None)
    return p


def run(args: argparse.Namespace) -> int:
    if args.msg_file:
        msg = Path(args.msg_file).read_text()
    else:
        msg = sys.stdin.read()
    errors = lint(msg)
    if errors:
        for e in errors:
            print(f"  ✗ {e}")
        logger.error(TOOL_ID, f"lint failed: {len(errors)}")
        return 1
    print("✅ commit message ok")
    logger.done(TOOL_ID, "lint passed")
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
