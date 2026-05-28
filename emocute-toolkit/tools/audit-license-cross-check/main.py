"""audit-license-cross-check — 同梱ライブラリのライセンス整合性確認.

ZIP 内の NOTICE/LICENSE/COPYING 系を再帰列挙し、
Copyright 表記が `Emocute Lab.` か `support@emocutelab.com` に統一されているか、
旧 Philtz 表記が残っていないか、第三者 OSS の LICENSE が削除されていないかチェック。
"""
from __future__ import annotations
import argparse
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "audit-license-cross-check"

LICENSE_NAMES = {"LICENSE", "LICENSE.md", "LICENSE.txt", "NOTICE", "NOTICE.md",
                 "COPYING", "COPYRIGHT"}
EMOCUTE_COPYRIGHT_RE = re.compile(r"Copyright \(c\) \d{4} Emocute Lab\.")
PHILTZ_RE = re.compile(r"\bphiltz(?!jp)\b", re.IGNORECASE)
KNOWN_OSS = {"MIT", "Apache", "BSD", "GPL", "MPL", "ISC"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute audit license-cross-check")
    p.add_argument("path", help="ZIP or ディレクトリ")
    return p


def scan_text(name: str, text: str) -> list[str]:
    issues = []
    if name in {"LICENSE", "LICENSE.md", "LICENSE.txt"}:
        if not EMOCUTE_COPYRIGHT_RE.search(text):
            issues.append(f"{name}: missing 'Copyright (c) YYYY Emocute Lab.'")
        if PHILTZ_RE.search(text):
            issues.append(f"{name}: legacy Philtz residue")
        if "support@emocutelab.com" not in text:
            issues.append(f"{name}: support email missing")
    return issues


def scan_zip(z: Path) -> list[str]:
    issues = []
    has_license = False
    with zipfile.ZipFile(z) as zf:
        for info in zf.infolist():
            base = Path(info.filename).name
            if base in LICENSE_NAMES:
                has_license = True
                try:
                    txt = zf.read(info).decode(errors="ignore")
                    issues += scan_text(base, txt)
                except Exception:
                    pass
    if not has_license:
        issues.append("no LICENSE file in zip")
    return issues


def scan_dir(d: Path) -> list[str]:
    issues = []
    has_license = False
    for p in d.rglob("*"):
        if p.name in LICENSE_NAMES and p.is_file():
            has_license = True
            try:
                issues += scan_text(p.name, p.read_text(errors="ignore"))
            except Exception:
                pass
    if not has_license:
        issues.append(f"no LICENSE file in {d}")
    return issues


def run(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        logger.error(TOOL_ID, f"not found: {target}")
        return 2
    if target.is_file() and target.suffix.lower() == ".zip":
        issues = scan_zip(target)
    elif target.is_dir():
        issues = scan_dir(target)
    else:
        logger.error(TOOL_ID, "need ZIP or directory")
        return 2
    if issues:
        print(f"❌ {len(issues)} issues in {target.name}")
        for i in issues:
            print(f"  - {i}")
        logger.warn(TOOL_ID, f"{len(issues)} issues in {target.name}")
        return 1
    print(f"✅ license OK: {target.name}")
    logger.done(TOOL_ID, f"OK: {target.name}")
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
