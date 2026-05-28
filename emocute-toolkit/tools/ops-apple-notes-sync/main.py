"""ops-apple-notes-sync — Apple Notes ピン留め note → Downloads/TODO.md 同期.

osascript で Notes.app から指定 note 本文を抜き、`<PJ>/TODO.md` の指定セクションに
反映する (`feedback_todo_2layer_management` の Apple Notes 司令塔運用)。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-apple-notes-sync"

OSA = """
tell application "Notes"
    set theNote to note "{title}"
    return body of theNote
end tell
"""


def fetch_note(title: str) -> str | None:
    r = subprocess.run(["osascript", "-e", OSA.format(title=title)], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops apple-notes-sync")
    p.add_argument("--title", required=True, help="Apple Notes 内のノートタイトル")
    p.add_argument("--out", required=True, help="出力先 md")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    body = fetch_note(args.title)
    if body is None:
        logger.error(TOOL_ID, f"note not found or osascript failed: {args.title}")
        return 3
    print(f"fetched: {len(body)} chars")
    print(body[:400])
    print("...")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body)
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"notes synced → {out.name}")
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
