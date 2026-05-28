"""audit-zip-3axis — 販売物 ZIP の 3 軸監査（法的 / ブランド / 個人情報 + 不適切表現）.

spec: registry/audit/audit-zip-3axis.yaml
"""
from __future__ import annotations
import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "audit-zip-3axis"

# CLAUDE.md § 販売物リリース前監査 由来
BANNED = {
    "legal_third_party_ip": [
        "Stickerbush Symphony", "DKC2", "Hollow Knight",
        "Kikuo", "imoutoid", "Moe Shop", "Sweet William", "Burial",
    ],
    "brand_drug_names": [
        "Cannabis", "LSD", "Ketamine", "Mushroom", "MDMA",
        "大麻", "ザナックス", "ケタミン",
    ],
    "inappropriate_expressions": [
        "出来合いの目玉テンプレ", "素材となる目玉パーツ", "いい感じのやつ",
        "ヤバい", "業界を破壊する",
    ],
    "internal_codenames": ["溶けて", "keep it", "肺MV"],
}
PERSONAL_INFO_REGEX = [
    (r"/Users/emocute/", "personal_path"),
    (r"\b\d{3}-\d{4}-\d{4}\b", "phone_jp"),
    (r"\b\d{4}-\d{2}-\d{2}\b", "absolute_date"),
]
# allowlist (false positive 除外)
ALLOW_SUBSTR = [
    "support@emocutelab.com", "emocutelab.com",
    "TR-808", "TR-909", "MPC", "Rhodes", "DX7", "MS-20", "JP-8000",
]
# base64 埋込フィルタ用
BASE64_NOISE = re.compile(r"(?:octet-stream|application/|base64,|data:image)")
# 走査対象拡張子（テキストのみ）
TEXT_EXTS = {".md", ".txt", ".html", ".htm", ".json", ".yaml", ".yml",
             ".ts", ".tsx", ".js", ".jsx", ".py", ".csv", ".srt", ".vtt"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"emocute audit zip-3axis")
    p.add_argument("zip_path", help="監査対象 ZIP")
    p.add_argument("--apply", action="store_true",
                   help="NG ヒット時 terminal-notifier 通知（既定 dry）")
    p.add_argument("--json", action="store_true", help="machine-readable")
    p.add_argument("--keep-extract", action="store_true",
                   help="展開ディレクトリを残す（既定は _archive へ移動）")
    return p


def _scan_text(text: str) -> list[tuple[str, str, str]]:
    """returns [(axis, term, snippet)]"""
    hits: list[tuple[str, str, str]] = []
    for axis, words in BANNED.items():
        for w in words:
            lo = 0
            while True:
                idx = text.find(w, lo)
                if idx < 0:
                    break
                snippet_start = max(0, idx - 30)
                snippet = text[snippet_start: idx + len(w) + 30]
                if BASE64_NOISE.search(snippet):
                    lo = idx + len(w)
                    continue
                if any(a in snippet for a in ALLOW_SUBSTR):
                    lo = idx + len(w)
                    continue
                hits.append((axis, w, snippet.replace("\n", " ")))
                lo = idx + len(w)
    for pat, label in PERSONAL_INFO_REGEX:
        for m in re.finditer(pat, text):
            snippet = text[max(0, m.start() - 30): m.end() + 30]
            if BASE64_NOISE.search(snippet):
                continue
            if any(a in snippet for a in ALLOW_SUBSTR):
                continue
            hits.append(("personal_info", label, snippet.replace("\n", " ")))
    return hits


def scan_dir(root: Path) -> dict:
    findings: dict[str, list[dict]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        hits = _scan_text(text)
        if hits:
            findings.setdefault(str(path.relative_to(root)), []).extend(
                {"axis": a, "term": t, "snippet": s} for a, t, s in hits
            )
    return findings


def write_report(report_path: Path, zip_path: Path, findings: dict) -> None:
    lines = [
        f"# audit report: {zip_path.name}",
        f"date: {dt.date.today().isoformat()}",
        "",
    ]
    if not findings:
        lines.append("✅ 全項目クリア")
    else:
        total = sum(len(v) for v in findings.values())
        lines.append(f"❌ {total} hits across {len(findings)} files")
        lines.append("")
        for fname, items in findings.items():
            lines.append(f"## {fname}")
            for it in items:
                lines.append(f"- [{it['axis']}] **{it['term']}** ⇒ `{it['snippet']}`")
            lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


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
    zip_path = Path(args.zip_path).expanduser().resolve()
    if not zip_path.exists():
        logger.error(TOOL_ID, f"zip not found: {zip_path}")
        return 2
    if zip_path.suffix.lower() != ".zip":
        logger.warn(TOOL_ID, f"not a .zip (will still try): {zip_path.suffix}")

    today = dt.date.today().isoformat()
    extract_root = zip_path.parent / f".audit_{today}"
    extract_root.mkdir(exist_ok=True)
    extract_dir = extract_root / zip_path.stem
    extract_dir.mkdir(exist_ok=True)

    logger.info(TOOL_ID, f"extracting {zip_path.name} -> {extract_dir}")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile as e:
        logger.error(TOOL_ID, f"bad zip: {e}")
        return 2

    findings = scan_dir(extract_dir)
    report_path = extract_root / f"audit_report_{zip_path.stem}.md"
    write_report(report_path, zip_path, findings)

    if args.json:
        import json
        print(json.dumps({
            "zip": str(zip_path),
            "report": str(report_path),
            "findings": findings,
            "hit_count": sum(len(v) for v in findings.values()),
        }, ensure_ascii=False, indent=2))
    else:
        if not findings:
            print(f"✅ clean: {zip_path.name}")
        else:
            total = sum(len(v) for v in findings.values())
            print(f"❌ {total} hits in {len(findings)} files. report: {report_path}")
            for fname, items in list(findings.items())[:5]:
                print(f"  {fname}:")
                for it in items[:3]:
                    print(f"    [{it['axis']}] {it['term']}")

    # `.audit_<date>/` を `_archive/loose_<date>/` 配下に移動（keep-extract 未指定時）
    if not args.keep_extract:
        archive_root = zip_path.parent / "_archive" / f"loose_{today}"
        archive_root.mkdir(parents=True, exist_ok=True)
        target = archive_root / extract_root.name
        if target.exists():
            target = archive_root / f"{extract_root.name}_{dt.datetime.now().strftime('%H%M%S')}"
        shutil.move(str(extract_root), str(target))
        logger.info(TOOL_ID, f"archived: {target}")

    if findings:
        logger.warn(TOOL_ID, f"NG hits: {sum(len(v) for v in findings.values())}",
                    meta={"zip": str(zip_path)})
        if args.apply:
            notify("emocute audit NG", f"{zip_path.name}: see {report_path.name}")
        return 2
    logger.done(TOOL_ID, f"clean: {zip_path.name}")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {e}")
        if args.json:
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
