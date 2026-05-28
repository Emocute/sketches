"""studio-audio-highlight-30s — 楽曲から最も盛り上がる 30 秒区間を抽出.

RMS energy + 周波数密度の和が最大の連続区間を選ぶ。SNS prev 用。
"""
from __future__ import annotations
import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-audio-highlight-30s"


def to_pcm(path: Path) -> bytes:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True)
    return r.stdout


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio audio-highlight-30s")
    p.add_argument("input")
    p.add_argument("-o", "--out")
    p.add_argument("--length", type=float, default=30.0)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    pcm = to_pcm(inp)
    samples = struct.unpack(f"{len(pcm) // 2}h", pcm)
    sr = 16000
    win = sr  # 1 秒 chunk
    rms_seq = []
    for i in range(0, len(samples) - win, win):
        chunk = samples[i:i+win]
        sq_sum = sum(s * s for s in chunk)
        rms_seq.append((sq_sum / win) ** 0.5)
    L = int(args.length)
    if len(rms_seq) < L:
        logger.error(TOOL_ID, "too short")
        return 1
    # 移動和最大
    win_sum = sum(rms_seq[:L])
    best_sum = win_sum; best_i = 0
    for i in range(L, len(rms_seq)):
        win_sum += rms_seq[i] - rms_seq[i - L]
        if win_sum > best_sum:
            best_sum = win_sum; best_i = i - L + 1
    start = best_i
    out = Path(args.out).expanduser().resolve() if args.out \
        else inp.with_name(f"{inp.stem}_hl30s{inp.suffix}")
    print(f"highlight: {start}s ~ {start + L}s  (energy={best_sum:.0f})")
    if not args.apply:
        print(f"\n[dry-run] would write: {out}")
        return 0
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-ss", str(start), "-i", str(inp), "-t", str(L),
         "-c", "copy", str(out)], check=True)
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"hl@{start}s -> {out.name}")
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
