"""studio-fft-spectrum — 音源の FFT スペクトログラム画像を生成.

ミックス確認用。可聴域上限・低域過密・特定帯域突出を視覚化。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-fft-spectrum"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio fft-spectrum")
    p.add_argument("input")
    p.add_argument("-o", "--out")
    p.add_argument("--size", default="1920x540")
    p.add_argument("--mode", choices=["spectrum", "showspectrumpic", "showfreqs"],
                   default="showspectrumpic")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    out = Path(args.out).expanduser().resolve() if args.out \
        else inp.with_suffix(".spectrum.png")
    if args.mode == "showspectrumpic":
        af = f"showspectrumpic=s={args.size}:legend=1"
    elif args.mode == "showfreqs":
        af = f"showfreqs=s={args.size}:mode=line"
    else:
        af = f"showspectrum=s={args.size}"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(inp), "-lavfi", af,
           "-frames:v", "1", str(out)]
    if not args.apply:
        print(f"[dry-run] {inp.name} → {out.name}  mode: {args.mode}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-300:]}")
        return 3
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"spectrum -> {out.name}")
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
