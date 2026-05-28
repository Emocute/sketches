"""visual-concat-fade — 複数動画を crossfade 連結.

ffmpeg xfade フィルタで隣接動画を crossfade 連結。
audio は acrossfade で合わせる。
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-concat-fade"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual concat-fade")
    p.add_argument("inputs", nargs="+", help="動画ファイル（順番通り）")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--duration", type=float, default=1.0, help="crossfade 長 (s)")
    p.add_argument("--transition", default="fade",
                   choices=["fade", "wipeleft", "wiperight", "dissolve",
                            "fadeblack", "fadewhite", "smoothleft", "smoothright"])
    p.add_argument("--apply", action="store_true")
    return p


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=False,
    )
    return float(r.stdout.strip()) if r.stdout.strip() else 0.0


def build_filter(inputs: list[Path], duration: float, transition: str) -> tuple[str, str, str]:
    """returns (filter_complex_str, final_v_label, final_a_label)"""
    durs = [probe_duration(p) for p in inputs]
    # xfade を順次連結
    v_chain = []
    a_chain = []
    cur_v = "[0:v]"
    cur_a = "[0:a]"
    offset = 0.0
    for i in range(1, len(inputs)):
        offset += durs[i - 1] - duration
        new_v = f"[v{i}]"
        new_a = f"[a{i}]"
        v_chain.append(
            f"{cur_v}[{i}:v]xfade=transition={transition}:duration={duration}"
            f":offset={offset:.3f}{new_v}"
        )
        a_chain.append(
            f"{cur_a}[{i}:a]acrossfade=d={duration}{new_a}"
        )
        cur_v = new_v
        cur_a = new_a
    flt = ";".join(v_chain + a_chain)
    return flt, cur_v, cur_a  # type: ignore[return-value]


def run(args: argparse.Namespace) -> int:
    inputs = [Path(x).expanduser().resolve() for x in args.inputs]
    missing = [p for p in inputs if not p.exists()]
    if missing:
        logger.error(TOOL_ID, f"missing: {missing}")
        return 2
    if len(inputs) < 2:
        logger.error(TOOL_ID, "need >= 2 inputs")
        return 2
    out = Path(args.out).expanduser().resolve()

    flt, final_v, final_a = build_filter(inputs, args.duration, args.transition)  # type: ignore
    cmd = ["ffmpeg", "-y", "-hide_banner"]
    for p in inputs:
        cmd += ["-i", str(p)]
    cmd += ["-filter_complex", flt,
            "-map", final_v, "-map", final_a,
            "-c:v", "libx264", "-crf", "18", "-c:a", "aac",
            str(out)]

    print(f"concat {len(inputs)} clips with {args.transition} fade ({args.duration}s)")
    print(f"out: {out}")

    if not args.apply:
        print(f"\n[dry-run] filter_complex preview:\n  {flt[:300]}...")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-400:]}")
        print(r.stderr[-400:])
        return 3
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"concat -> {out.name}")
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
