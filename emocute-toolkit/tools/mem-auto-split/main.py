"""mem-auto-split — MEMORY.md 200 行超で古い topic を _archive/ に分離.

spec: registry/mem/mem-auto-split.yaml
"""
from __future__ import annotations
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "mem-auto-split"

MEMORY_ROOT = Path.home() / ".claude" / "projects" / "-Users-emocute-Downloads" / "memory"
INDEX = MEMORY_ROOT / "MEMORY.md"
SECTION_RE = re.compile(r"^(##+)\s+(.+)$", re.MULTILINE)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)(?:#[^)]+)?\)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute mem auto-split")
    p.add_argument("--apply", action="store_true", help="実書込（既定 dry-run）")
    p.add_argument("--target-lines", type=int, default=180,
                   help="目標行数（既定 180、buffer 込）")
    p.add_argument("--recent-days", type=int, default=30,
                   help="この期間内に編集された memory ファイルを含む section は守る")
    return p


def parse_sections(text: str) -> list[tuple[int, str, str, int, int]]:
    """returns [(level, title, body, start_line, end_line)]"""
    lines = text.splitlines()
    matches = []
    for i, line in enumerate(lines):
        m = re.match(r"^(##+)\s+(.+)$", line)
        if m:
            matches.append((i, len(m.group(1)), m.group(2)))
    sections = []
    for idx, (start, level, title) in enumerate(matches):
        end = matches[idx + 1][0] if idx + 1 < len(matches) else len(lines)
        body = "\n".join(lines[start: end])
        sections.append((level, title, body, start, end))
    return sections


def section_max_mtime(body: str) -> float:
    """body 内で言及されている memory/*.md の mtime 最新."""
    latest = 0.0
    for m in LINK_RE.finditer(body):
        href = m.group(2)
        p = (MEMORY_ROOT / href).resolve()
        if p.exists() and p.is_file():
            mt = p.stat().st_mtime
            if mt > latest:
                latest = mt
    return latest


def run(args: argparse.Namespace) -> int:
    if not INDEX.exists():
        logger.error(TOOL_ID, f"MEMORY.md not found: {INDEX}")
        return 2
    text = INDEX.read_text(encoding="utf-8")
    lines = text.splitlines()
    n = len(lines)
    print(f"MEMORY.md: {n} lines (target: {args.target_lines})")

    if n <= args.target_lines:
        logger.done(TOOL_ID, f"under threshold ({n} <= {args.target_lines})")
        print("✅ no split needed")
        return 0

    sections = parse_sections(text)
    # h2 のみを移送対象
    h2 = [s for s in sections if s[0] == 2]
    print(f"found {len(h2)} h2 sections")

    now = dt.datetime.now().timestamp()
    recent_threshold = now - args.recent_days * 86400

    candidates = []
    for level, title, body, start, end in h2:
        mt = section_max_mtime(body)
        # mt==0 (リンクなし or 全部 missing) は移送候補にしない（壊れる可能性）
        if mt == 0:
            continue
        if mt >= recent_threshold:
            continue  # 直近活動あり → 守る
        candidates.append((mt, title, body, start, end))

    candidates.sort()  # 古い順
    print(f"split candidates: {len(candidates)} sections (oldest first)")

    to_split: list[tuple[float, str, str, int, int]] = []
    projected = n
    for c in candidates:
        if projected <= args.target_lines:
            break
        sec_lines = c[4] - c[3]
        # 1 行リンクで置換するので -sec_lines+1
        projected -= (sec_lines - 1)
        to_split.append(c)

    if not to_split:
        print("⚠️ over threshold but no eligible section to split (all recent)")
        logger.warn(TOOL_ID, "no eligible section to split")
        return 1

    yyyymm = dt.datetime.now().strftime("%Y%m")
    archive_dir = MEMORY_ROOT / "_archive" / yyyymm
    archive_file = archive_dir / "MEMORY_split.md"

    print(f"\nwill split {len(to_split)} sections → {archive_file}")
    for mt, title, body, _, _ in to_split:
        age_days = int((now - mt) / 86400)
        print(f"  - {title}  ({age_days}d old)")

    if not args.apply:
        print("\n[dry-run] use --apply to actually split")
        logger.info(TOOL_ID, f"dry-run: would split {len(to_split)} sections")
        return 0

    archive_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    chunk = [f"\n\n<!-- split from MEMORY.md on {today} -->"]
    for _, title, body, _, _ in to_split:
        chunk.append(body)
    archive_existing = archive_file.read_text(encoding="utf-8") if archive_file.exists() else ""
    archive_file.write_text(archive_existing + "\n".join(chunk) + "\n",
                            encoding="utf-8")

    # MEMORY.md 側: 該当 section を 1 行リンクに置換
    drop_ranges = sorted([(s, e) for _, _, _, s, e in to_split], reverse=True)
    new_lines = lines[:]
    for s, e in drop_ranges:
        title = re.match(r"^##\s+(.+)$", new_lines[s]).group(1)
        anchor = re.sub(r"[^a-zA-Z0-9-]+", "-", title).strip("-").lower()
        replacement = f"- [{title}](_archive/{yyyymm}/MEMORY_split.md#{anchor}) — split {today}"
        new_lines[s:e] = [replacement]

    INDEX.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    new_n = len(new_lines)
    print(f"\n✅ done: {n} -> {new_n} lines, archived to {archive_file}")
    logger.done(TOOL_ID, f"split {len(to_split)} sections, {n}->{new_n}")
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
