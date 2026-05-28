"""internal-tool-template-gen — 新規 tool のスキャフォールド生成.

`tools/_template/` を基に `tools/<new-id>/main.py` と
`registry/<category>/<new-id>.yaml` を生成。`registry/_status.yaml` への
追記も自動。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "internal-tool-template-gen"

CATEGORIES = ["audit", "release", "price", "studio", "visual", "sale",
              "site", "game", "mem", "ops", "comm", "infra", "research", "internal"]

TEMPLATE_MAIN = '''"""{tool_id} — {summary}."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "{tool_id}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute {category} {short_name}")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    if not args.apply:
        print("[dry-run]")
        return 0
    logger.done(TOOL_ID, "ok")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {{e}}")
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute internal tool-template-gen")
    p.add_argument("tool_id", help="例: visual-color-grader")
    p.add_argument("--summary", required=True)
    p.add_argument("--priority", default="med", choices=["high", "med", "low"])
    p.add_argument("--phase", type=int, default=5)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    tid = args.tool_id
    if "-" not in tid:
        logger.error(TOOL_ID, f"tool_id must contain '-': {tid}")
        return 2
    category = tid.split("-", 1)[0]
    if category not in CATEGORIES:
        logger.error(TOOL_ID, f"unknown category prefix: {category}")
        return 2
    short_name = tid.split("-", 1)[1]
    root = Path(__file__).resolve().parents[2]
    tool_dir = root / "tools" / tid
    if tool_dir.exists():
        logger.error(TOOL_ID, f"already exists: {tool_dir}")
        return 1
    main_py = tool_dir / "main.py"
    status_yaml = root / "registry" / "_status.yaml"
    new_entry = f"  {tid}: {{ phase: {args.phase}, category: {category}, priority: {args.priority}, status: planned }}"
    print(f"would create:")
    print(f"  {main_py.relative_to(root)}")
    print(f"  + entry in registry/_status.yaml: {new_entry}")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    tool_dir.mkdir(parents=True, exist_ok=True)
    main_py.write_text(TEMPLATE_MAIN.format(
        tool_id=tid, summary=args.summary, category=category, short_name=short_name))
    if status_yaml.exists():
        with status_yaml.open("a") as f:
            f.write("\n" + new_entry + "\n")
    print(f"✅ created {tool_dir}")
    logger.done(TOOL_ID, f"scaffold {tid}")
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
