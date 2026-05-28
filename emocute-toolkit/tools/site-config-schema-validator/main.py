"""site-config-schema-validator — nuxt.config / runtimeConfig の schema 検査.

期待 key (production: emocutelab.com / preview: *.vercel.app / API keys)
が揃っているか、欠けがあれば fail。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "site-config-schema-validator"

EXPECTED = ["public", "siteUrl", "stripePublishableKey", "supabaseUrl", "supabaseAnonKey"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site config-schema-validator")
    p.add_argument("nuxt_config")
    return p


def run(args: argparse.Namespace) -> int:
    p = Path(args.nuxt_config).expanduser().resolve()
    if not p.exists():
        logger.error(TOOL_ID, f"not found: {p}")
        return 2
    text = p.read_text(errors="ignore")
    missing = []
    for key in EXPECTED:
        if not re.search(rf"\b{re.escape(key)}\b", text):
            missing.append(key)
    if missing:
        print(f"⚠ missing config keys: {missing}")
        logger.warn(TOOL_ID, f"missing: {missing}")
        return 1
    print(f"✅ all expected keys present ({len(EXPECTED)})")
    logger.done(TOOL_ID, "config ok")
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
