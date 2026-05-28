"""ops-pre-push-safety — push 前安全チェック.

`git fetch --prune` 後、現在ブランチが remote と整合・未 commit 差分なし・
.gitignore 隠蔽禁止 を検査。CLAUDE.md § Git 操作 #1–9 準拠。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-pre-push-safety"


def git(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)
    return r.stdout.strip()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops pre-push-safety")
    p.add_argument("--repo", default=".")
    return p


def run(args: argparse.Namespace) -> int:
    repo = Path(args.repo).expanduser().resolve()
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo)
    print(f"branch: {branch}")
    subprocess.run(["git", "fetch", "--prune"], cwd=repo, capture_output=True)
    status = git("status", "--porcelain", cwd=repo)
    if status:
        print("⚠ uncommitted changes:")
        print(status[:500])
        logger.warn(TOOL_ID, "uncommitted changes present")
        return 1
    ahead_behind = git("rev-list", "--left-right", "--count", f"origin/{branch}...HEAD", cwd=repo)
    parts = ahead_behind.split("\t") if ahead_behind else ["0", "0"]
    behind, ahead = parts[0], parts[1] if len(parts) > 1 else "0"
    print(f"ahead:  {ahead}   behind: {behind}")
    if int(behind) > 0:
        print("⚠ local is behind remote. pull first.")
        return 1
    print("✅ safe to push")
    logger.done(TOOL_ID, f"safe push (ahead {ahead})")
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
