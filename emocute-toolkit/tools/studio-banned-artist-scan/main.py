"""studio-banned-artist-scan — Suno プロンプト/歌詞の banned_artist_names.txt 検証.

Studio/tools/banned_artist_names.txt と suno_render.py 既存実装をベースに、
任意のテキスト・ファイル・ディレクトリを一括スキャン。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import config, logger  # noqa: E402

TOOL_ID = "studio-banned-artist-scan"

BANNED_LIST_DEFAULT = "tools/banned_artist_names.txt"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio banned-artist-scan")
    p.add_argument("path", nargs="?",
                   help="走査対象（ファイル/ディレクトリ）。省略時 cwd")
    p.add_argument("--list", help="banned リスト (default Studio/tools/banned_artist_names.txt)")
    p.add_argument("--exts", default=".txt,.md,.json,.yaml,.yml,.html",
                   help="走査拡張子 csv")
    p.add_argument("--json", action="store_true")
    return p


def load_banned(path: Path) -> list[str]:
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        names.append(s)
    return names


def scan_text(text: str, names: list[str]) -> list[tuple[str, int]]:
    hits: list[tuple[str, int]] = []
    lo = text.lower()
    for n in names:
        idx = 0
        while True:
            i = lo.find(n.lower(), idx)
            if i < 0:
                break
            line_no = lo.count("\n", 0, i) + 1
            hits.append((n, line_no))
            idx = i + len(n)
    return hits


def run(args: argparse.Namespace) -> int:
    if args.list:
        list_path = Path(args.list).expanduser().resolve()
    else:
        try:
            list_path = config.pj_path("Studio") / BANNED_LIST_DEFAULT
        except KeyError:
            logger.error(TOOL_ID, "Studio PJ not configured")
            return 2
    if not list_path.exists():
        logger.error(TOOL_ID, f"banned list not found: {list_path}")
        return 2

    target = Path(args.path).expanduser().resolve() if args.path else Path.cwd()
    if not target.exists():
        logger.error(TOOL_ID, f"target not found: {target}")
        return 2

    names = load_banned(list_path)
    print(f"loaded {len(names)} banned artist names from {list_path.name}")

    exts = {e.strip().lower() for e in args.exts.split(",")}
    findings: dict[str, list[tuple[str, int]]] = {}

    files: list[Path] = []
    if target.is_file():
        files = [target]
    else:
        for p in target.rglob("*"):
            if not p.is_file():
                continue
            if any(part.startswith(".") or part in {"node_modules", "_archive"} for part in p.relative_to(target).parts):
                continue
            if p.suffix.lower() in exts:
                files.append(p)

    print(f"scanning {len(files)} files in {target}")
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits = scan_text(text, names)
        if hits:
            rel = str(p.relative_to(target)) if target.is_dir() else p.name
            findings[rel] = hits

    if args.json:
        import json
        print(json.dumps({"target": str(target), "findings": findings,
                          "names_loaded": len(names)},
                         ensure_ascii=False, indent=2))
    else:
        if not findings:
            print("✅ clean")
        else:
            total = sum(len(h) for h in findings.values())
            print(f"\n❌ {total} hits in {len(findings)} files:")
            for f, hits in findings.items():
                uniq = sorted({n for n, _ in hits})
                print(f"  {f}: {', '.join(uniq[:5])}")

    if findings:
        logger.error(TOOL_ID, f"banned artist hits: {len(findings)} files")
        return 2
    logger.done(TOOL_ID, f"clean ({len(files)} files scanned)")
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
