"""visual-mediarecorder-seg-concat — MediaRecorder の chunk-segment 群を結合.

ブラウザ録画で 1 秒刻みに保存した webm chunks をフレーム抜けなしで結合。
ffmpeg concat demuxer + Genpts で seek 復元。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-mediarecorder-seg-concat"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual mediarecorder-seg-concat")
    p.add_argument("pattern", help="例: 'rec/chunk_*.webm'")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--mp4", action="store_true", help="MP4 に変換 (default webm)")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    p = Path(args.pattern).expanduser()
    chunks = sorted(p.parent.glob(p.name))
    if not chunks:
        logger.error(TOOL_ID, f"no chunks match {args.pattern}")
        return 2
    out = Path(args.out).expanduser().resolve()
    print(f"chunks: {len(chunks)}  out: {out}")

    if not args.apply:
        for c in chunks[:5]:
            print(f"  {c.name}")
        if len(chunks) > 5:
            print(f"  ... ({len(chunks) - 5} more)")
        print("\n[dry-run]")
        return 0
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
        for c in chunks:
            tmp.write(f"file '{c.resolve()}'\n")
        list_path = tmp.name
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.mp4:
        cmd = ["ffmpeg", "-y", "-hide_banner",
               "-fflags", "+genpts", "-f", "concat", "-safe", "0",
               "-i", list_path,
               "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
               "-c:v", "libx264", "-crf", "18",
               "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", str(out)]
    else:
        cmd = ["ffmpeg", "-y", "-hide_banner",
               "-fflags", "+genpts", "-f", "concat", "-safe", "0",
               "-i", list_path, "-c", "copy", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    Path(list_path).unlink(missing_ok=True)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-300:]}")
        return 3
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"concat {len(chunks)} -> {out.name}")
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
