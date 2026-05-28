"""visual-lut-color-grading — .cube LUT を ffmpeg で動画に適用.

filmlook / teal-orange / vintage 等のカラーグレーディング preset を一発適用。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-lut-color-grading"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual lut-color-grading")
    p.add_argument("input")
    p.add_argument("--lut", required=True, help=".cube file path")
    p.add_argument("-o", "--out")
    p.add_argument("--strength", type=float, default=1.0,
                   help="LUT 適用強度 (0-1, default 1.0)")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    lut = Path(args.lut).expanduser().resolve()
    if not inp.exists() or not lut.exists():
        logger.error(TOOL_ID, f"missing: {inp} or {lut}")
        return 2
    out = Path(args.out).expanduser().resolve() if args.out \
        else inp.with_name(f"{inp.stem}_lut{inp.suffix}")
    # strength: split → lut3d → blend
    if args.strength >= 1.0:
        vf = f"lut3d='{lut}'"
    else:
        vf = (f"split=2[a][b];[b]lut3d='{lut}'[c];"
              f"[a][c]blend=all_expr='A*(1-{args.strength})+B*{args.strength}'")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", str(inp),
           "-vf", vf,
           "-c:v", "libx264", "-crf", "18", "-c:a", "copy", str(out)]
    if not args.apply:
        print(f"[dry-run] {inp.name} + {lut.name} (strength {args.strength}) → {out.name}")
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
