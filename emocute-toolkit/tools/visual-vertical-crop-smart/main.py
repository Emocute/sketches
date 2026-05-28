"""visual-vertical-crop-smart — 16:9 → 9:16 縦動画への smart crop.

中央切出のみ。複雑な顔追跡は HarmonyScope の motion detection で別途。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-vertical-crop-smart"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual vertical-crop-smart")
    p.add_argument("input")
    p.add_argument("-o", "--out")
    p.add_argument("--mode", choices=["center", "left", "right", "letterbox"],
                   default="center")
    p.add_argument("--target", default="1080x1920")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    out = Path(args.out).expanduser().resolve() if args.out \
        else inp.with_name(f"{inp.stem}_v{inp.suffix or '.mp4'}")
    tw, th = (int(x) for x in args.target.split("x"))

    if args.mode == "letterbox":
        vf = (f"scale={tw}:-2:force_original_aspect_ratio=decrease,"
              f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:black")
    else:
        # crop to vertical aspect of target then scale
        # 縦動画は ih を基準に幅を絞る
        if args.mode == "center":
            crop = f"crop=ih*{tw}/{th}:ih:(iw-ih*{tw}/{th})/2:0"
        elif args.mode == "left":
            crop = f"crop=ih*{tw}/{th}:ih:0:0"
        else:  # right
            crop = f"crop=ih*{tw}/{th}:ih:iw-ih*{tw}/{th}:0"
        vf = f"{crop},scale={tw}:{th}"

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-i", str(inp),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "18",
        "-c:a", "copy",
        str(out),
    ]
    print(f"input: {inp.name}  mode: {args.mode}  target: {args.target}")
    if not args.apply:
        print(f"\n[dry-run]  $ ffmpeg ... -vf {vf} {out}")
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
