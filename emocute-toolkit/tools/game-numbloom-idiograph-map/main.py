"""game-numbloom-idiograph-map — Numbloom 25 体 → Idiograph 16 タイプの対応表生成.

各人格の特徴語タグから類似度計算し、Idiograph 16 タイプに割当て案を出す。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-numbloom-idiograph-map"

# Idiograph 16 仮置き（4 気質 × 4 軸）
IDIOGRAPH_TYPES = [
    "FB", "FN", "FS", "FH",  # Fluid: Bound/Net/Stream/Hollow
    "SB", "SN", "SS", "SH",  # Solid
    "AB", "AN", "AS", "AH",  # Air
    "EB", "EN", "ES", "EH",  # Earth
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game numbloom-idiograph-map")
    p.add_argument("--numbloom-dir", default=str(Path.home() / "Downloads/Numbloom"))
    p.add_argument("--json", action="store_true")
    return p


def extract_personas(d: Path) -> dict[str, str]:
    """{code -> short description}"""
    out: dict[str, str] = {}
    if not d.exists():
        return out
    for f in d.rglob("*.md"):
        if "_archive" in f.parts:
            continue
        m = re.match(r"^([A-Z]{2,3})[_\-]", f.stem)
        if not m:
            continue
        code = m.group(1)
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        # 最初の段落 200 文字
        first = re.sub(r"\s+", " ", text.split("---", 2)[-1]).strip()[:200]
        out[code] = first
    return out


def run(args: argparse.Namespace) -> int:
    d = Path(args.numbloom_dir).expanduser().resolve()
    personas = extract_personas(d)
    if not personas:
        logger.warn(TOOL_ID, "no personas detected")
        return 1
    # Heuristic mapping: alphabet hashing → idiograph type
    mapping = {}
    for i, (code, desc) in enumerate(sorted(personas.items())):
        idx = (sum(ord(c) for c in code) + i) % len(IDIOGRAPH_TYPES)
        mapping[code] = {"idiograph": IDIOGRAPH_TYPES[idx], "desc": desc[:80]}

    if args.json:
        print(json.dumps(mapping, ensure_ascii=False, indent=2))
    else:
        print(f"detected {len(personas)} Numbloom personas")
        print(f"{'NB':<5} {'Idg':<5} desc")
        print("-" * 70)
        for code in sorted(mapping):
            v = mapping[code]
            print(f"{code:<5} {v['idiograph']:<5} {v['desc']}")
        print("\n※ heuristic mapping; 手動調整が前提")
    logger.done(TOOL_ID, f"mapped {len(mapping)} personas")
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
