"""ops-failure-mode-early-check — 既知の failure mode 早期検出.

memory `feedback_*` の失敗パターン（se-piace、wobble bass、システム声、
シネマティック提案、ABCDE 列挙、待機アナウンス 等）をテキストから grep し、
販売物・ドラフトに紛れ込んでないかチェック。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-failure-mode-early-check"

PATTERNS = {
    "se-piace": r"se[\s-]?piace",
    "wobble_bass": r"\bwobble\s+bass\b|reese\s+growl",
    "cinematic_default": r"\bcinematic\b.*\b(intro|build)\b",
    "system_voice": r"システム声|機械的に",
    "abcde_enum": r"^(?:[A-E][\.\)]\s.+\n){3,}",
    "no_waiting_announce": r"(?:待機|待ちます|お待ちします)",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops failure-mode-early-check")
    p.add_argument("path", help="file or directory")
    p.add_argument("--ext", default="md,txt,html")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser().resolve()
    exts = {f".{e}" for e in args.ext.split(",")}
    files = [root] if root.is_file() else [f for f in root.rglob("*") if f.is_file() and f.suffix in exts]
    findings: list[tuple[Path, str]] = []
    for f in files:
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for name, pat in PATTERNS.items():
            if re.search(pat, text, flags=re.MULTILINE | re.IGNORECASE):
                findings.append((f, name))
    print(f"scanned: {len(files)} files")
    if not findings:
        print("✅ no known failure-mode patterns found")
        logger.done(TOOL_ID, "no failure-modes")
        return 0
    for f, name in findings[:30]:
        print(f"  ⚠ {name:<20} {f}")
    logger.warn(TOOL_ID, f"failure-mode hits: {len(findings)}")
    return 1


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
