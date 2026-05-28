"""visual-webm-mp4-fallback — WebM → MP4 変換、odd 寸法対策内蔵.

MediaRecorder 録画後の標準 fallback。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-webm-mp4-fallback"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual webm-mp4-fallback")
    p.add_argument("input")
    p.add_argument("-o", "--out")
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--preset", default="slow")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    out = Path(args.out).expanduser().resolve() if args.out \
        else inp.with_suffix(".mp4")
    # 偶数化フィルタ + yuv420p（互換性）
    vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", str(inp),
           "-vf", vf,
           "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
           "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart",
           str(out)]
    if not args.apply:
        print(f"[dry-run] {inp.name} → {out.name}  (crf {args.crf})")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-300:]}")
        return 3
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"{inp.name} -> {out.name}")
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
