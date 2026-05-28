"""audit-old-philtz-residue — 旧 Philtz ブランド残置スキャン.

`philtz.com` URL、`Philtz Lab.` 表記、旧 email を全 tracked file から検出。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "audit-old-philtz-residue"

BANNED = [
    re.compile(r"\bphiltz\.com\b", re.IGNORECASE),
    re.compile(r"Philtz Lab\.?"),
    re.compile(r"@philtz\.com", re.IGNORECASE),
]
ALLOW_NAMES = {"philtzjp"}  # GitHub handle は履歴で残す
SCAN_EXTS = {".md", ".txt", ".html", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".tsx", ".vue"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute audit old-philtz-residue")
    p.add_argument("path", help="ディレクトリ")
    return p


def run(args: argparse.Namespace) -> int:
    d = Path(args.path).expanduser().resolve()
    if not d.is_dir():
        logger.error(TOOL_ID, f"not dir: {d}")
        return 2
    files = [f for f in d.rglob("*")
             if f.is_file() and f.suffix.lower() in SCAN_EXTS
             and "_archive" not in f.parts and ".git" not in f.parts]
    hits = []
    for f in files:
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for pat in BANNED:
            for m in pat.finditer(text):
                val = m.group(0).lower()
                if any(a in val for a in ALLOW_NAMES):
                    continue
                line = text[:m.start()].count("\n") + 1
                hits.append({"file": str(f.relative_to(d)), "line": line, "match": m.group(0)})
    if hits:
        print(f"❌ {len(hits)} philtz residues found")
        for h in hits[:30]:
            print(f"  {h['file']}:{h['line']}  '{h['match']}'")
        if len(hits) > 30:
            print(f"  ... ({len(hits) - 30} more)")
        logger.warn(TOOL_ID, f"{len(hits)} philtz residues in {d.name}")
        return 1
    print(f"✅ no philtz residue in {d.name} ({len(files)} files scanned)")
    logger.done(TOOL_ID, f"clean: {len(files)} files")
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
