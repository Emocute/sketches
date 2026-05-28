"""game-persona-cross-checker — Kagebu/Numbloom/Idiograph 横断の人格一貫性チェック.

各 PJ の persona 定義ファイルを読み、同じコードで定義が衝突していないか検証。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-persona-cross-checker"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game persona-cross-checker")
    p.add_argument("--kagebu", default=str(Path.home() / "Downloads/Kagebu/personas_master"))
    p.add_argument("--numbloom", default=str(Path.home() / "Downloads/Numbloom"))
    p.add_argument("--idiograph", default=str(Path.home() / "Downloads/Idiograph"))
    p.add_argument("--json", action="store_true")
    return p


def extract_codes(d: Path) -> dict[str, list[Path]]:
    """{code -> [files]}"""
    out: dict[str, list[Path]] = {}
    if not d.exists():
        return out
    code_re = re.compile(r"\b([A-Z]{2,3})(?:[:：\s])")
    for f in d.rglob("*.md"):
        if "_archive" in f.parts or ".git" in f.parts:
            continue
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        # ファイル名先頭が大文字コード
        m = re.match(r"^([A-Z]{2,3})[_\-]", f.stem)
        if m:
            out.setdefault(m.group(1), []).append(f)
            continue
        # 本文 frontmatter から
        for line in text.splitlines()[:30]:
            m = re.match(r"code:\s*([A-Z]{2,3})", line)
            if m:
                out.setdefault(m.group(1), []).append(f)
                break
    return out


def run(args: argparse.Namespace) -> int:
    pjs = {
        "kagebu": extract_codes(Path(args.kagebu).expanduser().resolve()),
        "numbloom": extract_codes(Path(args.numbloom).expanduser().resolve()),
        "idiograph": extract_codes(Path(args.idiograph).expanduser().resolve()),
    }
    # 全コード集合
    all_codes: dict[str, dict[str, list[str]]] = {}
    for pj, codes in pjs.items():
        for code, files in codes.items():
            all_codes.setdefault(code, {})[pj] = [str(f.name) for f in files]
    conflicts = {c: v for c, v in all_codes.items() if len(v) > 1}

    if args.json:
        print(json.dumps({"conflicts": conflicts, "all": all_codes},
                         ensure_ascii=False, indent=2))
    else:
        for pj, codes in pjs.items():
            print(f"{pj}: {len(codes)} personas")
        print(f"\n=== conflicts (same code in 2+ PJs) ===")
        for code, v in sorted(conflicts.items()):
            pjs_with = ", ".join(v.keys())
            print(f"  {code:<5}  in [{pjs_with}]")
        if not conflicts:
            print("  (none)")
    if conflicts:
        logger.warn(TOOL_ID, f"{len(conflicts)} code conflicts")
        return 1
    logger.done(TOOL_ID, "no conflict")
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
