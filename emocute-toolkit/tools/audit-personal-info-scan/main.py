"""audit-personal-info-scan — 配布物 PII スキャン.

実名・本名・住所・電話・絶対パス・絶対日付・関係者ハンドル等を grep。
販売物リリース前の必須監査ステップ。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "audit-personal-info-scan"

# 個人情報パターン
PATTERNS = {
    "abs_path": re.compile(r"/Users/[a-z]+/"),
    "abs_date_in_body": re.compile(r"\b20\d{2}-\d{2}-\d{2}\b"),
    "phone_jp": re.compile(r"\b0\d{1,4}-?\d{1,4}-?\d{4}\b"),
    "email": re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}
# email 許可ホワイトリスト
EMAIL_ALLOW = {"support@emocutelab.com", "noreply@anthropic.com",
               "emocute@emocutelab.com"}

SCAN_EXTS = {".md", ".txt", ".html", ".json", ".yaml", ".yml", ".csv"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute audit personal-info-scan")
    p.add_argument("path", help="ファイル or ディレクトリ")
    p.add_argument("--allow-email", action="append", default=[],
                   help="許可する email（複数 OK）")
    p.add_argument("--json", action="store_true")
    return p


def scan_file(p: Path, allow_emails: set[str]) -> list[dict]:
    try:
        text = p.read_text(errors="ignore")
    except Exception:
        return []
    hits = []
    for label, pat in PATTERNS.items():
        for m in pat.finditer(text):
            val = m.group(0)
            if label == "email" and val.lower() in allow_emails:
                continue
            line = text[:m.start()].count("\n") + 1
            hits.append({"type": label, "value": val, "line": line, "file": str(p)})
    return hits


def run(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        logger.error(TOOL_ID, f"not found: {target}")
        return 2
    files = [target] if target.is_file() else [
        f for f in target.rglob("*")
        if f.is_file() and f.suffix.lower() in SCAN_EXTS
    ]
    allow = EMAIL_ALLOW | {e.lower() for e in args.allow_email}
    all_hits = []
    for f in files:
        all_hits += scan_file(f, allow)

    if args.json:
        import json
        print(json.dumps(all_hits, indent=2))
    else:
        by_type: dict[str, int] = {}
        for h in all_hits:
            by_type[h["type"]] = by_type.get(h["type"], 0) + 1
        print(f"scanned {len(files)} files")
        print(f"hits: {len(all_hits)}")
        for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t:<20} {n}")
        if all_hits:
            print("\n--- sample hits (first 10) ---")
            for h in all_hits[:10]:
                short = h["file"].replace(str(Path.home()), "~")[:60]
                print(f"  [{h['type']}] {short}:{h['line']}  {h['value']}")

    if all_hits:
        logger.warn(TOOL_ID, f"{len(all_hits)} PII hits in {len(files)} files")
        return 1
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
