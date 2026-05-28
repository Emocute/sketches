"""visual-loudness-report — 動画の音声トラックの loudness 検査.

LUFS / TP / LRA を ffmpeg loudnorm で測定。YouTube/X 配信前の確認。
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

TOOL_ID = "visual-loudness-report"

# Platform LUFS targets
TARGETS = {
    "youtube": -14.0,
    "x":       -14.0,
    "tiktok":  -14.0,
    "spotify": -14.0,
    "apple":   -16.0,
    "broadcast": -23.0,
}


def measure(path: Path, target: float) -> dict:
    cmd = ["ffmpeg", "-hide_banner", "-i", str(path),
           "-af", f"loudnorm=I={target}:LRA=11:TP=-1.5:print_format=json",
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    # JSON is in stderr at the tail
    out = r.stderr
    start = out.rfind("{")
    if start < 0:
        return {"error": "no json in stderr"}
    end = out.rfind("}")
    try:
        return json.loads(out[start:end+1])
    except json.JSONDecodeError:
        return {"error": "json parse failed"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual loudness-report")
    p.add_argument("path", help="file or directory")
    p.add_argument("--platform", choices=list(TARGETS.keys()), default="youtube")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        logger.error(TOOL_ID, f"not found: {target}")
        return 2
    files = [target] if target.is_file() else [
        p for p in target.rglob("*")
        if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv", ".m4a", ".mp3", ".wav"}
    ]
    lufs_target = TARGETS[args.platform]
    rows = []
    for f in files:
        m = measure(f, lufs_target)
        if "error" in m:
            rows.append({"file": f.name, "error": m["error"]})
            continue
        try:
            i = float(m.get("input_i", 0))
            tp = float(m.get("input_tp", 0))
            lra = float(m.get("input_lra", 0))
        except (ValueError, TypeError):
            rows.append({"file": f.name, "error": "metric parse fail"})
            continue
        diff = i - lufs_target
        rows.append({"file": f.name, "lufs": round(i, 2),
                     "tp_db": round(tp, 2), "lra": round(lra, 2),
                     "diff_from_target": round(diff, 2)})
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'file':<40} {'LUFS':>7} {'TP':>6} {'LRA':>6} {'Δ':>6}")
        print("-" * 70)
        for r in rows:
            if "error" in r:
                print(f"{r['file'][:38]:<40} ERR: {r['error']}")
                continue
            warn = "⚠" if abs(r["diff_from_target"]) > 2 or r["tp_db"] > -1 else "✓"
            print(f"{r['file'][:38]:<40} {r['lufs']:>7.1f} {r['tp_db']:>6.1f} {r['lra']:>6.1f} {r['diff_from_target']:>+6.1f} {warn}")
    bad = sum(1 for r in rows if r.get("tp_db", -99) > -1 or abs(r.get("diff_from_target", 0)) > 2)
    if bad:
        logger.warn(TOOL_ID, f"{bad}/{len(rows)} files out of target ({args.platform})")
        return 1
    logger.done(TOOL_ID, f"{len(rows)} files within target")
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
