"""internal-changelog-gen — toolkit CHANGELOG.md 自動生成.

git log から `feat(toolkit)` 系 commit を抽出し、`CHANGELOG.md` に prepend。
最新 commit が既に CHANGELOG.md にあればスキップ。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "internal-changelog-gen"


def git_log(scope: str) -> list[str]:
    r = subprocess.run(
        ["git", "log", "--pretty=format:%h %s", f"--grep={scope}", "-30"],
        capture_output=True, text=True,
    )
    return r.stdout.splitlines()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute internal changelog-gen")
    p.add_argument("--scope", default="feat(toolkit)")
    p.add_argument("--out", default="CHANGELOG.md")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    lines = git_log(args.scope)
    if not lines:
        print("(no matching commits)")
        return 0
    header = f"## {date.today().isoformat()}\n"
    body = "\n".join(f"- {l}" for l in lines)
    block = f"{header}\n{body}\n\n"
    print(block[:600])
    if not args.apply:
        print("[dry-run]")
        return 0
    p = Path(args.out).expanduser().resolve()
    prev = p.read_text() if p.exists() else ""
    if header.strip() in prev:
        print(f"already has today's entry")
        return 0
    p.write_text(block + prev)
    print(f"✅ prepended to {p}")
    logger.done(TOOL_ID, f"changelog: {len(lines)} entries")
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
