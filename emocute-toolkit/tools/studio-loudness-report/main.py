"""studio-loudness-report — ffmpeg loudnorm で LUFS/LRA/TP レポート.

DSP 配信前のラウドネス確認用。-14 LUFS（Spotify/Apple Music 系基準）に
対する差分を表示。
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-loudness-report"

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac"}
TARGET_LUFS = -14.0  # Spotify / Apple Music


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio loudness-report")
    p.add_argument("path")
    p.add_argument("--target", type=float, default=TARGET_LUFS)
    p.add_argument("--json", action="store_true")
    return p


def analyze(path: Path) -> dict | None:
    cmd = [
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-af", "loudnorm=I=-14:LRA=11:TP=-1.5:print_format=json",
        "-f", "null", "-",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    # loudnorm JSON は stderr の末尾
    err = r.stderr
    m = re.search(r"\{[^{}]+\"input_i\"[^{}]+\}", err, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return {
        "input_i_lufs": float(data["input_i"]),
        "input_lra_lu": float(data["input_lra"]),
        "input_tp_dbfs": float(data["input_tp"]),
        "input_thresh_lufs": float(data["input_thresh"]),
    }


def run(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        logger.error(TOOL_ID, f"not found: {target}")
        return 2

    files: list[Path] = []
    if target.is_file():
        files = [target]
    else:
        for p in target.rglob("*"):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                files.append(p)

    print(f"analyzing {len(files)} audio file(s) ...")

    rows = []
    for f in files:
        info = analyze(f)
        if info is None:
            rows.append({"file": f.name, "error": "loudnorm parse failed"})
            continue
        diff = info["input_i_lufs"] - args.target
        info["file"] = f.name
        info["diff_from_target"] = round(diff, 2)
        info["target_lufs"] = args.target
        rows.append(info)

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(f"{'file':<40} {'LUFS':>8} {'LRA':>6} {'TP':>7} {'Δ tgt':>7}")
        print("-" * 70)
        for r in rows:
            if "error" in r:
                print(f"{r['file'][:38]:<40} {'ERR':>8}  {r['error']}")
                continue
            print(f"{r['file'][:38]:<40} "
                  f"{r['input_i_lufs']:>8.2f} "
                  f"{r['input_lra_lu']:>6.2f} "
                  f"{r['input_tp_dbfs']:>7.2f} "
                  f"{r['diff_from_target']:>+7.2f}")

    logger.done(TOOL_ID, f"analyzed {len(files)} files")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except FileNotFoundError as e:
        logger.error(TOOL_ID, f"binary not found: {e} (need ffmpeg)")
        return 3
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
