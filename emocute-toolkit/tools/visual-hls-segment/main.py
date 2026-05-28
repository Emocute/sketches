"""visual-hls-segment — 動画から HLS (m3u8 + ts) を生成.

サンプル試聴 / web preview 用。CDN 配信に直接食わせられる。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-hls-segment"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual hls-segment")
    p.add_argument("input")
    p.add_argument("-o", "--out-dir", required=True)
    p.add_argument("--seg-time", type=int, default=6, help="セグメント長 (s)")
    p.add_argument("--bitrate", default="2000k")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    out_dir = Path(args.out_dir).expanduser().resolve()
    m3u8 = out_dir / "index.m3u8"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", str(inp),
           "-c:v", "libx264", "-b:v", args.bitrate,
           "-c:a", "aac", "-b:a", "128k",
           "-hls_time", str(args.seg_time),
           "-hls_playlist_type", "vod",
           "-hls_segment_filename", str(out_dir / "seg_%03d.ts"),
           str(m3u8)]
    if not args.apply:
        print(f"[dry-run] {inp.name} → {out_dir}/  seg={args.seg_time}s br={args.bitrate}")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-300:]}")
        return 3
    n_segs = len(list(out_dir.glob("seg_*.ts")))
    print(f"✅ {n_segs} segments + {m3u8.name}")
    logger.done(TOOL_ID, f"hls {n_segs} segs -> {out_dir.name}")
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
