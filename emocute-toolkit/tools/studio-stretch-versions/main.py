"""studio-stretch-versions — テンポストレッチ違うバージョン量産.

1曲の WAV/MP3 を rubberband-cli or ffmpeg atempo で 0.9x/1.0x/1.1x/1.2x など。
Suno gen 後の試聴・比較・配布バリエーション制作用。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-stretch-versions"

DEFAULT_RATES = [0.9, 0.95, 1.05, 1.1]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio stretch-versions")
    p.add_argument("input")
    p.add_argument("--rates", nargs="+", type=float, default=DEFAULT_RATES)
    p.add_argument("--out-dir", default="stretched")
    p.add_argument("--apply", action="store_true")
    return p


def atempo_chain(rate: float) -> str:
    """atempo 範囲 0.5..2.0 のチェーンを構築"""
    if 0.5 <= rate <= 2.0:
        return f"atempo={rate}"
    parts = []
    r = rate
    while r > 2.0:
        parts.append("atempo=2.0")
        r /= 2.0
    while r < 0.5:
        parts.append("atempo=0.5")
        r *= 2.0
    parts.append(f"atempo={r}")
    return ",".join(parts)


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    out_dir = Path(args.out_dir).expanduser().resolve()
    jobs = []
    for r in args.rates:
        rstr = f"{r:.2f}x".replace(".", "_")
        target = out_dir / f"{inp.stem}_{rstr}{inp.suffix}"
        jobs.append((r, target))
    if not args.apply:
        print(f"[dry-run] {len(jobs)} versions")
        for r, t in jobs:
            print(f"  {r:.2f}x → {t.name}")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for r, target in jobs:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", str(inp), "-filter:a", atempo_chain(r),
               "-vn", str(target)]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            logger.error(TOOL_ID, f"ffmpeg failed at {r:.2f}x: {res.stderr[-200:]}")
            return 3
        print(f"  ✅ {r:.2f}x → {target.name}")
    logger.done(TOOL_ID, f"{len(jobs)} stretched versions")
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
