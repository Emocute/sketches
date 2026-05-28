"""visual-crf-auto — 目標ファイルサイズから libx264 CRF を自動選定.

X 1080p の 512MB / Twitter の 2 分等のサイズ制約に合うよう
2 パスでビットレート / CRF を推定。
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-crf-auto"

PLATFORM_LIMITS_MB = {
    "x": 512,
    "x_premium": 16384,
    "youtube": 128 * 1024,  # 128GB 実質無制限
    "discord": 25,
    "discord_nitro": 500,
    "tiktok": 287,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual crf-auto")
    p.add_argument("input")
    p.add_argument("-o", "--out")
    p.add_argument("--platform", choices=list(PLATFORM_LIMITS_MB.keys()),
                   default="x")
    p.add_argument("--target-mb", type=float,
                   help="明示的に MB 指定（platform を上書き）")
    p.add_argument("--apply", action="store_true")
    return p


def probe(path: Path) -> tuple[float, int, int]:
    """returns (duration, width, height)"""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=False,
    )
    d = json.loads(r.stdout)
    dur = float(d.get("format", {}).get("duration", 0))
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    return dur, int(v.get("width", 0)), int(v.get("height", 0))


def estimate_bitrate(target_mb: float, duration_s: float) -> int:
    """returns target_video_bitrate in kbps. audio に 128k 確保。"""
    total_kbits = target_mb * 8 * 1024  # MB -> kbit
    audio_kbits = 128 * duration_s
    video_kbits = total_kbits - audio_kbits
    return max(100, int(video_kbits / duration_s))


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    out = Path(args.out).expanduser().resolve() if args.out \
        else inp.with_name(f"{inp.stem}_{args.platform}.mp4")

    target_mb = args.target_mb or PLATFORM_LIMITS_MB[args.platform]
    dur, w, h = probe(inp)
    if dur <= 0:
        logger.error(TOOL_ID, "could not probe duration")
        return 3
    # safety margin 5%
    target_mb_safe = target_mb * 0.95
    vbr = estimate_bitrate(target_mb_safe, dur)
    print(f"input: {inp.name}  ({w}x{h}, {dur:.1f}s)")
    print(f"target: {target_mb}MB ({args.platform})  → {vbr} kbps")

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-i", str(inp),
        "-c:v", "libx264", "-preset", "slow",
        "-b:v", f"{vbr}k",
        "-maxrate", f"{int(vbr * 1.2)}k",
        "-bufsize", f"{vbr * 2}k",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out),
    ]

    if not args.apply:
        print(f"\n[dry-run] would write: {out}")
        print(f"  $ {' '.join(cmd[:10])} ...")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-300:]}")
        return 3
    size_mb = out.stat().st_size / 1e6
    mark = "✅" if size_mb <= target_mb else "⚠️"
    print(f"{mark} {out.name}: {size_mb:.1f} MB (target ≤ {target_mb})")
    logger.done(TOOL_ID, f"{out.name} {size_mb:.1f}MB / target {target_mb}")
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
