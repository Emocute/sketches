"""game-sketches-index — Sketches/ サブ PJ 一覧生成.

`Sketches/<PJ>/CONCEPT.md` を集めて Sketches トップの README 用住人リストを出力。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-sketches-index"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game sketches-index")
    p.add_argument("sketches_root")
    p.add_argument("-o", "--out", default="-")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.sketches_root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    sub_pjs = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith(("_", ".")):
            continue
        concept = d / "CONCEPT.md"
        first_line = ""
        if concept.exists():
            for line in concept.read_text(errors="ignore").splitlines():
                if line.strip() and not line.startswith("#"):
                    first_line = line.strip()[:80]
                    break
        sub_pjs.append((d.name, first_line, concept.exists()))
    lines = ["# Sketches 住人リスト", ""]
    for name, summary, has_concept in sub_pjs:
        flag = "" if has_concept else " ⚠ no CONCEPT.md"
        lines.append(f"- **{name}** — {summary or '(概要なし)'}{flag}")
    body = "\n".join(lines)
    if args.out == "-":
        print(body)
    else:
        Path(args.out).write_text(body)
        print(f"✅ wrote {args.out}")
    logger.done(TOOL_ID, f"sketches sub-pjs: {len(sub_pjs)}")
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
