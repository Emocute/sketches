"""studio-groove-half-auto-verify — グルーヴ半自動チェック.

オーディオの BPM をビートトラッキングで推定、想定 BPM との誤差で
groove の安定度を判定。`groove_verify_by_ear` 準拠で UI/メタ値を
信用せず実 PCM ベース。
"""
from __future__ import annotations
import argparse
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-groove-half-auto-verify"


def to_pcm(path: Path, sr: int = 8000) -> list[int]:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True, check=True)
    return list(struct.unpack(f"{len(r.stdout) // 2}h", r.stdout))


def detect_bpm(samples: list[int], sr: int) -> float:
    """エネルギーピーク間隔の中央値 → BPM 推定 (粗い)"""
    win = sr // 50  # 20ms
    energies = []
    for i in range(0, len(samples) - win, win):
        e = sum(abs(s) for s in samples[i:i+win]) / win
        energies.append(e)
    if not energies:
        return 0.0
    threshold = sorted(energies)[int(len(energies) * 0.85)]
    peaks = [i for i, e in enumerate(energies) if e > threshold]
    if len(peaks) < 4:
        return 0.0
    gaps = [b - a for a, b in zip(peaks, peaks[1:]) if b - a > 1]
    if not gaps:
        return 0.0
    gaps.sort()
    median_gap = gaps[len(gaps) // 2]
    sec_per_beat = median_gap * (win / sr)
    if sec_per_beat <= 0:
        return 0.0
    return 60.0 / sec_per_beat


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio groove-half-auto-verify")
    p.add_argument("input")
    p.add_argument("--expected-bpm", type=float, required=True)
    p.add_argument("--tolerance", type=float, default=2.0, help="許容 BPM 誤差")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    sr = 8000
    samples = to_pcm(inp, sr)
    bpm = detect_bpm(samples, sr)
    delta = abs(bpm - args.expected_bpm)
    status = "OK" if delta <= args.tolerance else "WARN"
    print(f"file:      {inp.name}")
    print(f"detected:  {bpm:.1f} BPM")
    print(f"expected:  {args.expected_bpm} BPM")
    print(f"delta:     {delta:.1f}  → {status}")
    print(f"\n⚠ 自動値は粗い。最終判定は実音源で耳確認 (groove_verify_by_ear)")
    logger.done(TOOL_ID, f"bpm: detect={bpm:.1f} expect={args.expected_bpm} delta={delta:.1f}")
    return 0 if delta <= args.tolerance else 1


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
