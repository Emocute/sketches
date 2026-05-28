"""visual-platform-versions — 1 つの動画から各 SNS 用 export 一気生成.

X 1080p / X Premium 4K / YouTube 4K / TikTok 9:16 / Discord 25MB 等。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-platform-versions"

PRESETS = {
    # name: (size, max_mb, suffix)
    "x_1080":     ("1920x1080",  512,  "_x1080"),
    "x_premium":  ("3840x2160",  16384, "_xpremium4k"),
    "youtube_4k": ("3840x2160",  0,    "_yt4k"),
    "tiktok":     ("1080x1920",  287,  "_tiktok"),
    "discord":    ("1280x720",   25,   "_discord"),
    "ig_square":  ("1080x1080",  100,  "_igsquare"),
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual platform-versions")
    p.add_argument("input")
    p.add_argument("--targets", default="x_1080,tiktok,discord",
                   help=f"csv from {list(PRESETS.keys())}")
    p.add_argument("--out-dir")
    p.add_argument("--apply", action="store_true")
    return p


def make_version(inp: Path, preset_name: str, out_dir: Path) -> bool:
    size, max_mb, suffix = PRESETS[preset_name]
    w, h = size.split("x")
    out = out_dir / f"{inp.stem}{suffix}.mp4"
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
          f"format=yuv420p")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(inp), "-vf", vf,
           "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-c:a", "aac", "-b:a", "128k",
           "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return False
    if max_mb and out.stat().st_size > max_mb * 1e6:
        # 再エンコード (target bitrate 推定)
        import json
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "json", str(out)],
                           capture_output=True, text=True)
        dur = float(json.loads(d.stdout)["format"]["duration"])
        vbr = int((max_mb * 0.9 * 8 * 1024 - 128 * dur) / dur)
        out2 = out.with_name(out.stem + "_fit.mp4")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(inp), "-vf", vf,
                        "-c:v", "libx264", "-preset", "slow",
                        "-b:v", f"{vbr}k", "-maxrate", f"{int(vbr*1.2)}k",
                        "-bufsize", f"{vbr*2}k",
                        "-c:a", "aac", "-b:a", "128k",
                        "-movflags", "+faststart", str(out2)],
                       check=False)
        out.unlink()
        out2.rename(out)
    return True


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    targets = [t.strip() for t in args.targets.split(",")]
    bad = [t for t in targets if t not in PRESETS]
    if bad:
        logger.error(TOOL_ID, f"unknown targets: {bad}")
        return 2
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else inp.parent
    print(f"input: {inp.name}")
    print(f"targets: {targets}")
    if not args.apply:
        for t in targets:
            size, mb, suf = PRESETS[t]
            print(f"  would write: {inp.stem}{suf}.mp4  ({size}, ≤{mb}MB)")
        print("\n[dry-run]")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for t in targets:
        success = make_version(inp, t, out_dir)
        print(f"  {'✅' if success else '❌'} {t}")
        if success: ok += 1
    logger.done(TOOL_ID, f"{ok}/{len(targets)} versions ok")
    return 0 if ok == len(targets) else 1


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
