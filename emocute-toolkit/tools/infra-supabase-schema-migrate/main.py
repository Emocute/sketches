"""infra-supabase-schema-migrate — Supabase schema 差分マイグレーション.

`Site/db/migrations/*.sql` を順次 apply。Supabase は DDL モーダル確認 +
`SELECT` 検証が必要 (`reference_supabase_ddl_modal`)。本ツールは plan 出力のみ、
実 apply は CLI/dashboard 経由。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "infra-supabase-schema-migrate"

VERSION_RE = re.compile(r"^(\d{4}_\d{2}_\d{2}|\d{14})_")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute infra supabase-schema-migrate")
    p.add_argument("migrations_dir")
    p.add_argument("--applied-log", default=".applied.txt")
    return p


def run(args: argparse.Namespace) -> int:
    d = Path(args.migrations_dir).expanduser().resolve()
    if not d.exists():
        logger.error(TOOL_ID, f"not found: {d}")
        return 2
    log = d / args.applied_log
    applied = set(log.read_text().splitlines()) if log.exists() else set()
    files = sorted(f for f in d.glob("*.sql") if VERSION_RE.match(f.name))
    pending = [f for f in files if f.name not in applied]
    print(f"total: {len(files)}  applied: {len(applied)}  pending: {len(pending)}")
    for f in pending:
        print(f"  ⏳ {f.name}")
    if not pending:
        print("(no pending migrations)")
    print("\nNEXT: dashboard 経由で順に apply 後、SELECT で検証 → .applied.txt に記録")
    logger.done(TOOL_ID, f"pending migrations: {len(pending)}")
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
