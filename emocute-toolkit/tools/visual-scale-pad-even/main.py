"""visual-scale-pad-even — 奇数解像度 → 偶数化（MediaRecorder 対策）.

spec: registry/visual/visual-scale-pad-even.yaml
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-scale-pad-even"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual scale-pad-even")
    p.add_argument("input")
    p.add_argument("output", nargs="?")
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--apply", action="store_true", help="実書込（既定 計算のみ）")
    return p


def probe_resolution(path: Path) -> tuple[int, int]:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(proc.stdout)
    s = info["streams"][0]
    return int(s["width"]), int(s["height"])


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"input not found: {inp}")
        return 2

    w, h = probe_resolution(inp)
    print(f"input {inp.name}: {w}x{h}")

    if w % 2 == 0 and h % 2 == 0:
        print("✅ already even, no re-encode needed")
        logger.done(TOOL_ID, f"already even {w}x{h}")
        return 0

    new_w = w - (w % 2)
    new_h = h - (h % 2)
    out = Path(args.output).expanduser().resolve() if args.output \
        else inp.with_name(f"{inp.stem}_even{inp.suffix or '.mp4'}")

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-i", str(inp),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-crf", str(args.crf),
        "-c:a", "copy",
        str(out),
    ]
    print(f"target: {new_w}x{new_h}  out: {out}")
    if not args.apply:
        print(f"\n[dry-run]  $ {' '.join(cmd)}")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {proc.stderr[-300:]}")
        return 3
    nw, nh = probe_resolution(out)
    print(f"✅ wrote {out.name}: {nw}x{nh}")
    logger.done(TOOL_ID, f"{w}x{h} -> {nw}x{nh}: {out.name}")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except FileNotFoundError as e:
        logger.error(TOOL_ID, f"binary not found: {e} (need ffmpeg/ffprobe)")
        return 3
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
