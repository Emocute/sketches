"""sale-cover-multi-size — ジャケ画像をプラットフォーム別サイズに一括書き出し.

3000×3000 のマスタージャケから Spotify (640) / Apple (3000) / YouTube
(1280×720) / X header (1500×500) など複数サイズを ffmpeg/Pillow で生成。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-cover-multi-size"

PRESETS = {
    "spotify_640":    "640x640",
    "apple_3000":     "3000x3000",
    "youtube_1280x720": "1280x720",
    "x_header_1500x500": "1500x500",
    "ogp_1200x630":   "1200x630",
    "booth_thumb_720": "720x720",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale cover-multi-size")
    p.add_argument("master", help="3000x3000 マスタージャケ")
    p.add_argument("--out-dir", default="covers")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.master).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    out_dir = Path(args.out_dir).expanduser().resolve()
    print(f"master: {src.name}")
    print(f"out:    {out_dir}/")
    for name, size in PRESETS.items():
        print(f"  • {name:<22s} → {src.stem}_{name}.jpg ({size})")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, size in PRESETS.items():
        out = out_dir / f"{src.stem}_{name}.jpg"
        w, h = map(int, size.split("x"))
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", str(src), "-vf", vf, "-q:v", "2", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            logger.error(TOOL_ID, f"{name} failed: {r.stderr[-200:]}")
            return 3
        print(f"  ✅ {name}")
    logger.done(TOOL_ID, f"{len(PRESETS)} sizes")
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
