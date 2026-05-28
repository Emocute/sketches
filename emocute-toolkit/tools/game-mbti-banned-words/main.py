"""game-mbti-banned-words — Idiograph MBTI 商標侵害語スキャナ.

spec: registry/game/game-mbti-banned-words.yaml
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import config, logger  # noqa: E402

TOOL_ID = "game-mbti-banned-words"

# 完全に一語として hit すべき単語 (大小文字保持)
BANNED_EXACT = [
    "MBTI", "Myers-Briggs", "Myers Briggs",
    "16Personalities", "16-Personalities", "16 Personalities",
    "NERIS",
    "INFJ", "ENTP", "INTJ", "ISFP", "ESFJ", "ENFP", "ISTJ",
    "ESFP", "ISTP", "ESTJ", "ESTP", "ISFJ", "INTP", "INFP",
    "ENFJ", "ENTJ",
    "性格分析プログラム",
]
# 文脈依存（MBTI 系統で使われる場合のみ NG）
BANNED_CONTEXTUAL = [
    ("Architect", r"\b(?:INTJ|MBTI|personality)\b"),
    ("Mediator", r"\b(?:INFP|MBTI|personality)\b"),
    ("Defender", r"\b(?:ISFJ|MBTI|personality)\b"),
]

# 監査対象拡張子
SALE_EXTS = {".md", ".txt", ".html", ".htm", ".json", ".yaml", ".yml",
             ".ts", ".tsx", ".js", ".jsx"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game mbti-banned-words")
    p.add_argument("path", nargs="?", help="スキャン対象（既定 Downloads/Idiograph）")
    p.add_argument("--json", action="store_true")
    p.add_argument("--notify", action="store_true")
    return p


def scan_text(text: str) -> list[tuple[str, int, str]]:
    """returns [(term, line_no, snippet)]"""
    hits: list[tuple[str, int, str]] = []
    lines = text.splitlines()
    for w in BANNED_EXACT:
        # 単語境界は ASCII の場合のみ。日本語語は単純 substring
        is_ascii = all(c.isascii() for c in w)
        pat = re.compile(rf"\b{re.escape(w)}\b") if is_ascii else re.compile(re.escape(w))
        for i, line in enumerate(lines, 1):
            if pat.search(line):
                hits.append((w, i, line.strip()[:200]))
    for w, ctx_pat in BANNED_CONTEXTUAL:
        ctx = re.compile(ctx_pat, re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            # 同じ行 or 周辺 3 行に context あれば NG
            window = "\n".join(lines[max(0, i - 3): i + 2])
            if re.search(rf"\b{re.escape(w)}\b", line) and ctx.search(window):
                hits.append((f"{w}(ctx)", i, line.strip()[:200]))
    return hits


def scan_dir(root: Path) -> dict[str, list[dict]]:
    findings: dict[str, list[dict]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        # スキップ対象
        rel = path.relative_to(root)
        parts = set(rel.parts)
        if any(p.startswith(".") or p in {"node_modules", "_archive", ".audit"} for p in parts):
            continue
        if path.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory() as td:
                tdp = Path(td)
                try:
                    with zipfile.ZipFile(path) as zf:
                        zf.extractall(tdp)
                except zipfile.BadZipFile:
                    continue
                sub = scan_dir(tdp)
                for f, items in sub.items():
                    findings[f"{rel}::{f}"] = items
            continue
        if path.suffix.lower() not in SALE_EXTS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits = scan_text(text)
        if hits:
            findings[str(rel)] = [
                {"term": t, "line": ln, "snippet": sn} for t, ln, sn in hits
            ]
    return findings


def is_sale_path(rel: str) -> bool:
    """販売対象判定: docs/, _drafts/, _ideas/ 以下はコメント扱いで warn のみ."""
    low = rel.lower()
    if any(low.startswith(d) for d in ("docs/", "_drafts/", "_ideas/", "tests/")):
        return False
    if "/_archive/" in low or "/_archive\\" in low:
        return False
    return True


def notify(title: str, msg: str) -> None:
    bin_ = "/opt/homebrew/bin/terminal-notifier"
    if not Path(bin_).exists():
        return
    try:
        subprocess.run([bin_, "-title", title, "-message", msg, "-sound", "Glass"],
                       check=False, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run(args: argparse.Namespace) -> int:
    if args.path:
        root = Path(args.path).expanduser().resolve()
    else:
        try:
            root = config.pj_path("Idiograph")
        except KeyError:
            logger.error(TOOL_ID, "PJ Idiograph not configured")
            return 2
    if not root.exists():
        logger.error(TOOL_ID, f"path not found: {root}")
        return 2

    print(f"scanning {root}")
    findings = scan_dir(root)
    sale_hits = {k: v for k, v in findings.items() if is_sale_path(k)}
    other_hits = {k: v for k, v in findings.items() if not is_sale_path(k)}

    if args.json:
        print(json.dumps({
            "scan_root": str(root),
            "sale_hits": sale_hits,
            "internal_hits": other_hits,
            "total_files": len(findings),
        }, ensure_ascii=False, indent=2))
    else:
        if not findings:
            print("✅ clean")
        else:
            print(f"\n❌ sale-path hits ({len(sale_hits)} files):")
            for f, hits in sale_hits.items():
                print(f"  {f}:")
                for h in hits[:5]:
                    print(f"    L{h['line']} [{h['term']}] {h['snippet'][:80]}")
            if other_hits:
                print(f"\n⚠️  internal-only hits ({len(other_hits)} files, docs/drafts):")
                for f in list(other_hits.keys())[:10]:
                    print(f"  {f} ({len(other_hits[f])} hits)")

    if sale_hits:
        logger.error(TOOL_ID, f"sale-path MBTI hits: {len(sale_hits)} files")
        if args.notify:
            notify("Idiograph MBTI hit", f"{len(sale_hits)} sale-path files")
        return 2
    if other_hits:
        logger.warn(TOOL_ID, f"internal hits: {len(other_hits)} files")
        return 1
    logger.done(TOOL_ID, "no MBTI banned terms")
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
