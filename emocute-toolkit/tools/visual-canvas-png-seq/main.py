"""visual-canvas-png-seq — PNG 連番 → 動画 ffmpeg まとめ.

Canvas / Three.js / Blender 等で吐いた PNG 連番を MP4/MOV にまとめる。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-canvas-png-seq"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual canvas-png-seq")
    p.add_argument("pattern", help="PNG パターン (例: 'out/frame_%%04d.png')")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--fps", type=int, default=60)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--audio", help="音声 mux 用 (省略可)")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser().resolve()
    cmd = ["ffmpeg", "-y", "-hide_banner",
           "-framerate", str(args.fps),
           "-start_number", str(args.start),
           "-i", args.pattern]
    if args.audio:
        a = Path(args.audio).expanduser().resolve()
        if not a.exists():
            logger.error(TOOL_ID, f"audio not found: {a}")
            return 2
        cmd += ["-i", str(a), "-c:a", "aac", "-b:a", "192k",
                "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "16",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            str(out)]
    if not args.apply:
        print(f"[dry-run] {args.pattern} @ {args.fps}fps → {out}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-300:]}")
        return 3
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"png-seq -> {out.name}")
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
