"""game-chord-dict-sqlite — コード辞書 SQLite 化.

`Studio/chord_dict/*.json` を SQLite に取り込んで chord/voicing/tag を索引化、
HarmonyScope/iOS 理論実験室から共通参照可能にする。
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-chord-dict-sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chords (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    voicing TEXT,
    tags TEXT,
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_symbol ON chords(symbol);
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game chord-dict-sqlite")
    p.add_argument("dict_root", help="chord_dict/")
    p.add_argument("-o", "--out", default="chord_dict.sqlite")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.dict_root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    files = list(root.rglob("*.json"))
    print(f"json files: {len(files)}")
    if not args.apply:
        print(f"[dry-run] would build {args.out}")
        return 0
    out = Path(args.out).expanduser().resolve()
    conn = sqlite3.connect(out)
    conn.executescript(SCHEMA)
    inserted = 0
    for f in files:
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        entries = data if isinstance(data, list) else [data]
        for e in entries:
            if not isinstance(e, dict) or "symbol" not in e:
                continue
            conn.execute(
                "INSERT INTO chords (symbol, voicing, tags, source) VALUES (?, ?, ?, ?)",
                (e["symbol"], json.dumps(e.get("voicing")), json.dumps(e.get("tags")), str(f.name)),
            )
            inserted += 1
    conn.commit()
    conn.close()
    print(f"✅ inserted {inserted} chord rows into {out}")
    logger.done(TOOL_ID, f"chord-dict sqlite: {inserted} rows")
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
