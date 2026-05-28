"""mem-index-verify — memory/*.md と MEMORY.md の整合性検証.

spec: registry/mem/mem-index-verify.yaml
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "mem-index-verify"

MEMORY_ROOT = Path.home() / ".claude" / "projects" / "-Users-emocute-Downloads" / "memory"
INDEX = MEMORY_ROOT / "MEMORY.md"
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)(?:#[^)]+)?\)")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute mem index-verify")
    p.add_argument("--json", action="store_true")
    p.add_argument("--notify", action="store_true",
                   help="ドリフト検出時 terminal-notifier")
    return p


def collect_index_links() -> set[Path]:
    """MEMORY.md から参照されている全 .md ファイルのパス（絶対）."""
    if not INDEX.exists():
        return set()
    text = INDEX.read_text(encoding="utf-8")
    paths: set[Path] = set()
    for m in LINK_RE.finditer(text):
        href = m.group(2)
        # 相対パス → MEMORY_ROOT 基点
        p = (MEMORY_ROOT / href).resolve()
        paths.add(p)
    return paths


def collect_archive_files() -> set[Path]:
    archive_dir = MEMORY_ROOT / "_archive"
    if not archive_dir.exists():
        return set()
    return {p.resolve() for p in archive_dir.rglob("*.md")}


def collect_all_memory_files() -> set[Path]:
    return {p.resolve() for p in MEMORY_ROOT.glob("*.md") if p.name != "MEMORY.md"}


def check_frontmatter_rules(path: Path) -> list[str]:
    """feedback / project の Why / How to apply 行抜けチェック."""
    issues: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"read error: {e}"]
    m = FRONTMATTER_RE.match(text)
    if not m:
        issues.append("frontmatter missing or malformed")
        return issues
    fm = m.group(1)
    mtype = re.search(r"^type:\s*(\w+)", fm, re.MULTILINE)
    if not mtype:
        issues.append("frontmatter missing 'type:' field")
        return issues
    type_ = mtype.group(1).strip()
    body = text[m.end():]
    if type_ in {"feedback", "project"}:
        if "**Why:**" not in body and "Why:" not in body:
            issues.append(f"{type_} memory missing 'Why:' line")
        if "**How to apply:**" not in body and "How to apply:" not in body:
            issues.append(f"{type_} memory missing 'How to apply:' line")
    return issues


def notify(title: str, msg: str) -> None:
    bin_ = "/opt/homebrew/bin/terminal-notifier"
    if not Path(bin_).exists():
        return
    try:
        subprocess.run([bin_, "-title", title, "-message", msg, "-sound", "Tink"],
                       check=False, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run(args: argparse.Namespace) -> int:
    if not MEMORY_ROOT.exists():
        logger.error(TOOL_ID, f"memory root not found: {MEMORY_ROOT}")
        return 2
    if not INDEX.exists():
        logger.error(TOOL_ID, f"MEMORY.md not found: {INDEX}")
        return 2

    indexed = collect_index_links()
    archived = collect_archive_files()
    all_top = collect_all_memory_files()

    # dead links: indexed が指す先で実在しないもの
    dead_links: list[str] = []
    for p in indexed:
        if not p.exists():
            try:
                rel = p.relative_to(MEMORY_ROOT)
            except ValueError:
                rel = p
            dead_links.append(str(rel))

    # orphan: 直下にあるが index にも archive にも無い
    orphan: list[str] = []
    for p in all_top:
        if p not in indexed and p not in archived:
            orphan.append(p.name)

    # frontmatter rule violations
    rule_violations: dict[str, list[str]] = {}
    for p in all_top:
        issues = check_frontmatter_rules(p)
        if issues:
            rule_violations[p.name] = issues

    # 重複（同じ tag 系の short hash）— heuristic: 同じ description 先頭 60 字
    desc_index: dict[str, list[str]] = {}
    for p in all_top:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        d = re.search(r"^description:\s*(.+)", m.group(1), re.MULTILINE)
        if not d:
            continue
        key = d.group(1).strip()[:60]
        desc_index.setdefault(key, []).append(p.name)
    duplicates = {k: v for k, v in desc_index.items() if len(v) > 1}

    # MEMORY.md 行数
    line_count = len(INDEX.read_text(encoding="utf-8").splitlines())
    over_limit = line_count > 200

    result = {
        "memory_md_line_count": line_count,
        "over_200_lines": over_limit,
        "indexed_count": len(indexed),
        "top_md_count": len(all_top),
        "dead_links": sorted(dead_links),
        "orphan_files": sorted(orphan),
        "rule_violations": rule_violations,
        "duplicates": duplicates,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"MEMORY.md: {line_count} lines"
              + (" ⚠️ over 200" if over_limit else ""))
        print(f"indexed links: {len(indexed)}  top *.md files: {len(all_top)}")
        if dead_links:
            print(f"\n❌ dead links ({len(dead_links)}):")
            for x in dead_links[:20]:
                print(f"  - {x}")
        if orphan:
            print(f"\n⚠️  orphan files ({len(orphan)}):")
            for x in orphan[:20]:
                print(f"  - {x}")
        if rule_violations:
            print(f"\n⚠️  rule violations ({len(rule_violations)}):")
            for fname, issues in list(rule_violations.items())[:10]:
                print(f"  - {fname}: {'; '.join(issues)}")
        if duplicates:
            print(f"\n⚠️  potential duplicates ({len(duplicates)} groups):")
            for k, files in list(duplicates.items())[:10]:
                print(f"  - [{k}...] {', '.join(files)}")
        if not (dead_links or orphan or rule_violations or duplicates or over_limit):
            print("\n✅ clean")

    severity = 0
    if over_limit or orphan or rule_violations:
        severity = max(severity, 1)
    if dead_links or duplicates:
        severity = max(severity, 2)

    if severity == 0:
        logger.done(TOOL_ID, "memory clean")
    elif severity == 1:
        logger.warn(TOOL_ID, f"warnings: orphan={len(orphan)} viol={len(rule_violations)} over={over_limit}")
        if args.notify:
            notify("memory drift", f"orphan {len(orphan)} / over200={over_limit}")
    else:
        logger.error(TOOL_ID, f"errors: dead={len(dead_links)} dup={len(duplicates)}")
        if args.notify:
            notify("memory drift ERROR", f"dead links {len(dead_links)} / dup {len(duplicates)}")
    return severity


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {e}")
        if args.json:
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
