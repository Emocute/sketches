"""game-numbloom-card-art-score — カードアートの一貫性スコア.

各 PNG カードアートのサイズ/色域/avg brightness を測って外れ値検出。
カード追加で「他と毛色違う」絵を放置しないため。
"""
from __future__ import annotations
import argparse
import statistics
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-numbloom-card-art-score"


def avg_brightness(path: Path) -> float:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", str(path), "-vf", "scale=64:64,format=gray",
         "-f", "rawvideo", "-"],
        capture_output=True, check=False)
    if r.returncode != 0 or not r.stdout:
        return -1
    data = r.stdout[:64*64]
    return sum(data) / len(data) if data else 0.0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game numbloom-card-art-score")
    p.add_argument("art_dir")
    p.add_argument("--threshold", type=float, default=2.0, help="±σ")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.art_dir).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    cards = list(root.glob("*.png")) + list(root.glob("*.jpg"))
    if not cards:
        logger.error(TOOL_ID, "no card art found")
        return 1
    rows = []
    for c in cards:
        b = avg_brightness(c)
        rows.append({"file": c.name, "brightness": round(b, 1)})
    bs = [r["brightness"] for r in rows if r["brightness"] >= 0]
    if not bs:
        logger.error(TOOL_ID, "ffmpeg failed on all")
        return 3
    mean = statistics.mean(bs)
    stdev = statistics.pstdev(bs) or 1
    print(f"cards:    {len(rows)}")
    print(f"mean:     {mean:.1f}  stdev: {stdev:.1f}")
    print(f"\noutliers (±{args.threshold}σ):")
    for r in rows:
        z = (r["brightness"] - mean) / stdev
        if abs(z) >= args.threshold:
            print(f"  ⚠ {r['file']:<32s}  brightness={r['brightness']:>5.1f}  z={z:+.2f}")
    logger.done(TOOL_ID, f"art score {len(rows)} cards, mean={mean:.0f}")
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
