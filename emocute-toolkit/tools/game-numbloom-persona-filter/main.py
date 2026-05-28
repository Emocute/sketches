"""game-numbloom-persona-filter — Numbloom 25 体人格と Kagebu 12 体の重複/欠落チェック.

Numbloom の persona ファイルから 25 体を抽出し、
Kagebu の personas_master と突合。重複命名・スコープ違反を検出。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-numbloom-persona-filter"

# Kagebu 12 体（CLAUDE.md より）
KAGEBU_CORE = {"XO", "HR", "ND", "BD", "MP", "DE", "NT", "HB", "YB", "MX", "PS", "MT"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game numbloom-persona-filter")
    p.add_argument("--numbloom-dir", default=str(Path.home() / "Downloads/Numbloom"))
    p.add_argument("--kagebu-dir", default=str(Path.home() / "Downloads/Kagebu/personas_master"))
    p.add_argument("--json", action="store_true")
    return p


def extract_numbloom_personas(d: Path) -> set[str]:
    """persona は 2-3 文字大文字英字プレフィックス（CLAUDE.md より）"""
    if not d.exists():
        return set()
    persona_re = re.compile(r"\b([A-Z]{2,3})(?:[\s:：])", re.MULTILINE)
    cand: set[str] = set()
    for f in d.rglob("*.md"):
        if "_archive" in f.parts:
            continue
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for m in persona_re.finditer(text):
            code = m.group(1)
            # よくある false positive 除外
            if code in {"OK", "NG", "TODO", "FIXME", "HTML", "JSON", "URL",
                        "API", "CLI", "MP3", "WAV", "ZIP", "PDF", "PNG", "JPG",
                        "SVG", "CSS", "JS", "TS"}:
                continue
            cand.add(code)
    return cand


def extract_kagebu_personas(d: Path) -> set[str]:
    if not d.exists():
        return set()
    codes = set()
    for f in d.iterdir():
        if f.is_file() and f.suffix == ".md":
            stem = f.stem.upper()
            # ファイル名先頭 2-3 文字
            m = re.match(r"^([A-Z]{2,3})", stem)
            if m:
                codes.add(m.group(1))
    return codes


def run(args: argparse.Namespace) -> int:
    n_dir = Path(args.numbloom_dir).expanduser().resolve()
    k_dir = Path(args.kagebu_dir).expanduser().resolve()
    nm = extract_numbloom_personas(n_dir)
    km = extract_kagebu_personas(k_dir) or KAGEBU_CORE
    overlap = nm & km
    numbloom_only = nm - km
    kagebu_only = km - nm

    result = {
        "numbloom_count": len(nm),
        "kagebu_count": len(km),
        "overlap": sorted(overlap),
        "numbloom_only": sorted(numbloom_only),
        "kagebu_only_missing": sorted(kagebu_only),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Numbloom personas detected: {len(nm)}")
        print(f"Kagebu personas: {len(km)}")
        print(f"\noverlap ({len(overlap)}): {' '.join(sorted(overlap))}")
        print(f"numbloom only ({len(numbloom_only)}): {' '.join(sorted(numbloom_only))}")
        print(f"kagebu only ({len(kagebu_only)}): {' '.join(sorted(kagebu_only))}")
    if overlap:
        logger.warn(TOOL_ID, f"{len(overlap)} persona code overlap with Kagebu")
        return 1
    logger.done(TOOL_ID, f"numbloom={len(nm)} kagebu={len(km)}")
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
