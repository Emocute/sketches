"""mem-stale-detect — memory ファイルの古さ検出.

最終更新 N 日以上のファイルを検出し、内容が陳腐化していないか確認するための一覧。
"""
from __future__ import annotations
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "mem-stale-detect"
MEMORY_DIR = Path.home() / ".claude/projects/-Users-emocute-Downloads/memory"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute mem stale-detect")
    p.add_argument("--days", type=int, default=60, help="しきい値 (default 60)")
    p.add_argument("--memory-dir", default=str(MEMORY_DIR))
    p.add_argument("--type", choices=["project", "feedback", "user", "reference", "all"],
                   default="project", help="project が陳腐化しやすい")
    return p


def detect_type(text: str) -> str:
    for line in text.splitlines()[:20]:
        if line.startswith("type:"):
            return line.split(":", 1)[1].strip()
    return ""


def run(args: argparse.Namespace) -> int:
    d = Path(args.memory_dir).expanduser().resolve()
    if not d.is_dir():
        logger.error(TOOL_ID, f"not dir: {d}")
        return 2
    now = dt.datetime.now()
    threshold = now - dt.timedelta(days=args.days)
    stale = []
    for f in d.glob("*.md"):
        if f.name == "MEMORY.md":
            continue
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        mtype = detect_type(text)
        if args.type != "all" and mtype != args.type:
            continue
        mtime = dt.datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < threshold:
            age_days = (now - mtime).days
            stale.append({"file": f.name, "age_days": age_days, "type": mtype})

    stale.sort(key=lambda x: -x["age_days"])
    if stale:
        print(f"{len(stale)} memory files older than {args.days} days (type={args.type})")
        for s in stale[:40]:
            print(f"  {s['age_days']:>4}d  [{s['type']:<10}] {s['file']}")
        if len(stale) > 40:
            print(f"  ... ({len(stale) - 40} more)")
        logger.warn(TOOL_ID, f"{len(stale)} stale memory files")
        return 1
    print(f"✅ no stale memory (type={args.type})")
    logger.done(TOOL_ID, "no stale")
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
