"""comm-discord-arata-snapshot — Arata DM スナップショット.

`reference_arata_discord_fetch` 経由で取得した DM 履歴を md にダンプ。
`feedback_arata_dm_terminal_only` 準拠でグループに混ぜない、ターミナル専用。
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "comm-discord-arata-snapshot"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute comm discord-arata-snapshot")
    p.add_argument("--out-dir", default="_drafts/arata_dm")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    print(f"out_dir: {args.out_dir}")
    print(f"limit:   {args.limit}")
    print("(本ツールは実 fetch を行わない skeleton。実 fetch は reference_arata_discord_fetch の手順参照)")
    if not args.apply:
        print("[dry-run]")
        return 0
    out = Path(args.out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    snapshot = out / f"snapshot_{ts}.md"
    snapshot.write_text(f"# Arata DM snapshot {ts}\n\n(empty placeholder — populate via fetch script)\n")
    print(f"✅ wrote {snapshot}")
    logger.done(TOOL_ID, f"arata snapshot {ts}")
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
