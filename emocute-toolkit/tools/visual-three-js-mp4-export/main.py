"""visual-three-js-mp4-export — Three.js canvas を MP4 にエクスポート.

Three.js デモの canvas を MediaRecorder で録って WebM → MP4 変換。
プレビュー用 URL を Playwright で開く想定。本ツールは render 後の MP4 化
パイプラインのみ。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-three-js-mp4-export"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual three-js-mp4-export")
    p.add_argument("webm", help="MediaRecorder 出力 .webm")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.webm).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"webm not found: {src}")
        return 2
    out = Path(args.out).expanduser().resolve()
    cmd = ["ffmpeg", "-y", "-hide_banner",
           "-i", str(src),
           "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf),
           "-pix_fmt", "yuv420p",
           "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
           "-movflags", "+faststart",
           str(out)]
    if not args.apply:
        print(f"[dry-run] {src.name} → {out.name}  (crf={args.crf})")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-300:]}")
        return 3
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"three-mp4 -> {out.name}")
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
