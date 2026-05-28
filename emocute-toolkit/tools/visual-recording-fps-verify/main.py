"""visual-recording-fps-verify — 録画動画の FPS 安定性を検査.

ffprobe で各フレームの DTS を抽出 → フレーム間隔の分散・drop 検出。
OBS/Cmd+Shift+5/MediaRecorder の品質確認。
"""
from __future__ import annotations
import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-recording-fps-verify"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual recording-fps-verify")
    p.add_argument("input")
    p.add_argument("--expect-fps", type=float, default=30.0)
    p.add_argument("--tolerance", type=float, default=0.5,
                   help="平均 fps の許容偏差 (default 0.5)")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "frame=pkt_dts_time",
         "-of", "csv=p=0", str(inp)],
        capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        logger.error(TOOL_ID, "ffprobe failed")
        return 3
    timestamps = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line or line == "N/A":
            continue
        try:
            timestamps.append(float(line))
        except ValueError:
            continue
    if len(timestamps) < 2:
        logger.error(TOOL_ID, "no frame DTS")
        return 3
    diffs = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps) - 1)]
    diffs = [d for d in diffs if d > 0]
    mean_d = statistics.mean(diffs)
    std_d = statistics.stdev(diffs) if len(diffs) > 1 else 0
    fps = 1 / mean_d if mean_d else 0
    # drop 検出: 平均間隔の 1.8 倍以上
    drops = sum(1 for d in diffs if d > mean_d * 1.8)
    jitter = std_d / mean_d * 100 if mean_d else 0

    result = {
        "file": inp.name,
        "frames": len(timestamps),
        "duration_s": round(timestamps[-1] - timestamps[0], 2),
        "fps_measured": round(fps, 3),
        "fps_expected": args.expect_fps,
        "drops": drops,
        "jitter_pct": round(jitter, 2),
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"file: {inp.name}")
        print(f"  frames: {result['frames']}  duration: {result['duration_s']}s")
        print(f"  fps measured: {result['fps_measured']}  (expect {args.expect_fps})")
        print(f"  drops: {drops}  jitter: {jitter:.2f}%")
    if abs(fps - args.expect_fps) > args.tolerance or drops > 0:
        logger.warn(TOOL_ID, f"unstable: fps={fps:.2f} drops={drops}")
        return 1
    logger.done(TOOL_ID, f"stable: fps={fps:.2f} drops=0")
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
