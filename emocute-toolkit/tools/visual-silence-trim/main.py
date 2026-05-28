"""visual-silence-trim — ffmpeg silencedetect → 自動 trim.

spec: registry/visual/visual-silence-trim.yaml
"""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-silence-trim"

SILENCE_START_RE = re.compile(r"silence_start:\s*([\d.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*([\d.]+)")
DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):([\d.]+)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual silence-trim")
    p.add_argument("input")
    p.add_argument("output", nargs="?")
    p.add_argument("--noise", default="-40dB")
    p.add_argument("--duration", type=float, default=0.5,
                   help="最小無音長 (s)")
    p.add_argument("--apply", action="store_true", help="実書込（既定 計算のみ）")
    return p


def detect_silence(input_path: Path, noise: str, dur: float) -> tuple[list[float], list[float], float]:
    """returns (silence_ends, silence_starts, total_duration)"""
    cmd = [
        "ffmpeg", "-hide_banner", "-i", str(input_path),
        "-af", f"silencedetect=noise={noise}:d={dur}",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    err = proc.stderr
    starts = [float(m.group(1)) for m in SILENCE_START_RE.finditer(err)]
    ends = [float(m.group(1)) for m in SILENCE_END_RE.finditer(err)]
    duration = 0.0
    m = DURATION_RE.search(err)
    if m:
        h, mn, s = m.groups()
        duration = int(h) * 3600 + int(mn) * 60 + float(s)
    return ends, starts, duration


def compute_trim(ends: list[float], starts: list[float], total: float) -> tuple[float, float] | None:
    """先頭の silence_end が trim 開始、末尾の silence_start が trim 終了."""
    # 冒頭から続く無音: silence_start=0 で silence_end が最初の音
    head = 0.0
    if ends and (not starts or ends[0] <= (starts[0] if starts else total)):
        # 先頭がそもそも無音 → silence_start=0 のはず
        # 単純に最初の silence_end を head とする（安全策: 0.0 を含まない場合は据置）
        if starts and starts[0] < 0.1:
            head = ends[0]
    # 末尾無音: silence_start が音終端、silence_end が total に近い
    tail = total
    if starts and ends:
        last_start = starts[-1]
        last_end = ends[-1] if len(ends) > len(starts) - 1 else total
        # 末尾の silence_start から total まで無音 → tail = last_start
        if abs(last_end - total) < 1.0 or last_end >= total - 0.5:
            tail = last_start
    if total <= 0:
        return None
    if tail - head < 0.2:  # 全編無音相当
        return None
    return head, tail


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"input not found: {inp}")
        return 2
    out = Path(args.output).expanduser().resolve() if args.output \
        else inp.with_name(f"{inp.stem}_trim{inp.suffix}")

    print(f"detecting silence in {inp.name} (noise={args.noise}, d={args.duration})...")
    ends, starts, total = detect_silence(inp, args.noise, args.duration)
    if total == 0:
        logger.error(TOOL_ID, "ffmpeg failed to read input or duration unknown")
        return 3
    print(f"  duration: {total:.2f}s,  silence segments: {len(ends)} ends, {len(starts)} starts")

    trim = compute_trim(ends, starts, total)
    if trim is None:
        logger.error(TOOL_ID, "all-silent or invalid; refusing to write empty output")
        return 1
    head, tail = trim
    print(f"  trim range: {head:.3f}s → {tail:.3f}s  (cut {head:.2f}s head + {total - tail:.2f}s tail)")

    if not args.apply:
        print(f"\n[dry-run] would write: {out}")
        print(f"  ffmpeg -ss {head} -to {tail} -i {inp} -c copy {out}")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-ss", f"{head}", "-to", f"{tail}",
        "-i", str(inp), "-c", "copy",
        str(out),
    ]
    print(f"  $ {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg trim failed: {proc.stderr[-300:]}")
        return 3

    # verify
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        capture_output=True, text=True, check=False,
    )
    new_dur = float(probe.stdout.strip() or 0)
    print(f"\n✅ wrote {out.name} ({new_dur:.2f}s)")
    logger.done(TOOL_ID, f"{inp.name} -> {out.name} ({total:.2f}s -> {new_dur:.2f}s)")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except FileNotFoundError as e:
        logger.error(TOOL_ID, f"binary not found: {e} (need ffmpeg/ffprobe in PATH)")
        return 3
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
