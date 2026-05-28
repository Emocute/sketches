"""release-changelog-prepend — CHANGELOG.md に新バージョン節を prepend.

旧節は残し、最新を上に積む。版下作成漏れ防止。
"""
from __future__ import annotations
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "release-changelog-prepend"

HEADER_RE = "# CHANGELOG"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute release changelog-prepend")
    p.add_argument("path", help="CHANGELOG.md path")
    p.add_argument("--version", required=True, help="例: 1.9.4")
    p.add_argument("--date", help="YYYY-MM-DD (default 今日)")
    p.add_argument("--note", action="append", default=[], help="箇条書き (複数 OK)")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser().resolve()
    date = args.date or dt.date.today().isoformat()
    bullets = args.note or ["(notes pending)"]
    new_section = f"## v{args.version} — {date}\n\n"
    for b in bullets:
        new_section += f"- {b}\n"
    new_section += "\n"

    if path.exists():
        cur = path.read_text()
    else:
        cur = "# CHANGELOG\n\n"

    # 重複バージョンチェック
    if f"## v{args.version}" in cur:
        logger.warn(TOOL_ID, f"v{args.version} already in CHANGELOG")
        return 1

    # # CHANGELOG 直後に挿入
    if cur.startswith("# "):
        lines = cur.split("\n", 2)
        header = lines[0] + "\n" + (lines[1] if len(lines) > 1 else "") + "\n"
        body = lines[2] if len(lines) > 2 else ""
        out_text = header + new_section + body
    else:
        out_text = "# CHANGELOG\n\n" + new_section + cur

    if not args.apply:
        print(f"[dry-run] would prepend v{args.version} to {path}")
        print("---")
        print(new_section)
        return 0
    path.write_text(out_text)
    print(f"✅ prepended v{args.version} to {path}")
    logger.done(TOOL_ID, f"v{args.version} -> {path.name}")
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
