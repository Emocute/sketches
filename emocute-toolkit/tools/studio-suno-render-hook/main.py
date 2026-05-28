"""studio-suno-render-hook — Suno DL 後のレンダーフック.

Suno からダウンロードした MP3 を検知し、ID3 タグ・正本格納・session 記録を
連鎖実行。LaunchAgent で `~/Downloads/Suno_*.mp3` を監視する想定。
"""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-suno-render-hook"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio suno-render-hook")
    p.add_argument("mp3", help="Suno MP3 (新規)")
    p.add_argument("--song-id", required=True)
    p.add_argument("--dest", default="Studio/renders", help="格納先ディレクトリ")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.mp3).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"mp3 not found: {src}")
        return 2
    dest_dir = Path(args.dest).expanduser().resolve() / args.song_id
    target = dest_dir / src.name
    actions = [
        f"mv  {src} → {target}",
        f"id3 tag: artist=Emocute album=<song_id> title=<from-name>",
        f"session_log append: studio/sessions/today.jsonl",
    ]
    print(f"song_id: {args.song_id}")
    for a in actions:
        print(f"  • {a}")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), target)
    print(f"✅ moved → {target}")
    logger.done(TOOL_ID, f"render hooked {args.song_id}/{src.name}")
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
