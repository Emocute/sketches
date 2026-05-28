"""studio-arrangement-density — 楽曲の編曲密度（同時に鳴る楽器数）の時系列を解析.

ステム分離は不要。スペクトラルフラックスの推移で「密度」を近似。
イントロ静かでサビ盛り上がり、等の構造把握。
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

TOOL_ID = "studio-arrangement-density"


def to_pcm(path: Path) -> tuple[list[int], int]:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "8000", "-"],
        capture_output=True, check=True)
    samples = struct.unpack(f"{len(r.stdout) // 2}h", r.stdout)
    return list(samples), 8000


def spectral_flux(samples: list[int], sr: int, win: int = 1024) -> list[float]:
    """簡易フラックス（窓ごとのエネルギー差絶対値の平均）"""
    fluxes = []
    prev_sum = 0
    for i in range(0, len(samples) - win, win):
        chunk = samples[i:i+win]
        e = sum(abs(s) for s in chunk) / win
        fluxes.append(abs(e - prev_sum))
        prev_sum = e
    return fluxes


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio arrangement-density")
    p.add_argument("input")
    p.add_argument("--bins", type=int, default=20, help="セクション分割数")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    samples, sr = to_pcm(inp)
    flux = spectral_flux(samples, sr)
    if not flux:
        logger.warn(TOOL_ID, "too short")
        return 1
    # bins ごとに平均化
    step = max(1, len(flux) // args.bins)
    sections = []
    for i in range(0, len(flux), step):
        chunk = flux[i:i+step]
        if chunk:
            sections.append(sum(chunk) / len(chunk))
    max_v = max(sections) or 1
    if args.json:
        print(json.dumps({"bins": sections, "max": max_v}, indent=2))
    else:
        print(f"arrangement density (▁ low – █ high)")
        chars = "▁▂▃▄▅▆▇█"
        for i, v in enumerate(sections):
            n = int(v / max_v * (len(chars) - 1))
            print(f"  bin {i:02d}  {chars[n]}  {v / max_v * 100:>5.1f}%")
    logger.done(TOOL_ID, f"density bins={len(sections)}")
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
