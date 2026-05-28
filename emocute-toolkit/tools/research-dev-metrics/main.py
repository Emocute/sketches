"""research-dev-metrics — Git commit/diff から開発メトリクス算出.

直近 N 日の commit 数・著者別比率・カテゴリ別 (feat/fix/docs) 分布を出力。
"""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "research-dev-metrics"

TYPE_RE = re.compile(r"^(feat|fix|perf|refactor|docs|style|test|chore|ci|build)")


def git_log(repo: Path, days: int) -> list[tuple[str, str]]:
    r = subprocess.run(
        ["git", "log", f"--since={days}.days.ago", "--pretty=format:%an\t%s"],
        capture_output=True, text=True, cwd=repo,
    )
    out = []
    for line in r.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            out.append((parts[0], parts[1]))
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute research dev-metrics")
    p.add_argument("--repo", default=".")
    p.add_argument("--days", type=int, default=30)
    return p


def run(args: argparse.Namespace) -> int:
    repo = Path(args.repo).expanduser().resolve()
    commits = git_log(repo, args.days)
    print(f"commits (last {args.days} days): {len(commits)}")
    authors = Counter(a for a, _ in commits)
    types = Counter()
    for _, msg in commits:
        m = TYPE_RE.match(msg)
        types[m.group(1) if m else "other"] += 1
    print(f"\nby author:")
    for a, n in authors.most_common(10):
        print(f"  {n:>5}  {a}")
    print(f"\nby type:")
    for t, n in types.most_common():
        print(f"  {n:>5}  {t}")
    logger.done(TOOL_ID, f"metrics: {len(commits)} commits")
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
