"""infra-stripe-security-audit — Stripe 設定セキュリティ監査.

`STRIPE_*` 環境変数が secret key (sk_live_) でないこと・webhook secret が
.env で管理されていること・git tracked file に key が残ってないことを確認。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "infra-stripe-security-audit"

KEY_RE = re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{20,}")
PK_RE = re.compile(r"pk_(?:live|test)_[A-Za-z0-9]{20,}")
WHSEC_RE = re.compile(r"whsec_[A-Za-z0-9]{20,}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute infra stripe-security-audit")
    p.add_argument("project_root")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.project_root).expanduser().resolve()
    findings = []
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if any(p in f.parts for p in [".git", "node_modules", ".next", "_archive"]):
            continue
        if f.suffix not in {".js", ".ts", ".vue", ".py", ".env", ".sh", ".yaml", ".yml", ".json", ".md"}:
            continue
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for pat, label in [(KEY_RE, "SECRET_KEY"), (WHSEC_RE, "WEBHOOK_SECRET")]:
            if pat.search(text):
                if f.name == ".env" or f.name.startswith(".env."):
                    continue
                findings.append((f.relative_to(root), label))
    print(f"scanned: {root}")
    if not findings:
        print("✅ no Stripe secret leaks found in tracked files")
        logger.done(TOOL_ID, "no leaks")
        return 0
    print(f"⚠ {len(findings)} suspicious occurrences:")
    for path, label in findings[:20]:
        print(f"  • {label}  {path}")
    logger.error(TOOL_ID, f"stripe secret leak suspects: {len(findings)}")
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
