"""studio-suno-length-verify — MP3 1分尺 / 歌詞 2分尺 検証.

feedback_suno_mp3_1min_lyrics_2min 準拠。ffprobe で audio duration を確認。
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-suno-length-verify"

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio suno-length-verify")
    p.add_argument("path", help="audio file or directory")
    p.add_argument("--target-min", type=float, default=1.0,
                   help="期待最低尺 minutes (default 1.0 = MP3 bed)")
    p.add_argument("--target-max", type=float, default=2.5,
                   help="期待最大尺 minutes (default 2.5)")
    p.add_argument("--json", action="store_true")
    return p


def probe_duration(path: Path) -> float | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=False, timeout=30,
        )
        return float(r.stdout.strip()) if r.stdout.strip() else None
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return None


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

    print(f"checking {len(files)} audio file(s) "
          f"[{args.target_min:.1f}min ≤ dur ≤ {args.target_max:.1f}min]")

    results = []
    bad = 0
    for f in files:
        d = probe_duration(f)
        if d is None:
            results.append({"file": str(f.name), "duration_s": None,
                            "status": "unreadable"})
            bad += 1
            continue
        dm = d / 60
        status = "ok"
        if dm < args.target_min:
            status = "too_short"
            bad += 1
        elif dm > args.target_max:
            status = "too_long"
            bad += 1
        results.append({"file": str(f.name), "duration_s": round(d, 2),
                        "duration_min": round(dm, 2), "status": status})

    if args.json:
        print(json.dumps({"results": results, "bad": bad, "total": len(files)},
                         ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = {"ok": "✅", "too_short": "⚠️ short",
                    "too_long": "⚠️ long", "unreadable": "❌"}[r["status"]]
            dur = f"{r['duration_min']:.2f}min" if r.get("duration_min") else "?"
            print(f"  {mark}  {dur:>10}  {r['file']}")
        if bad:
            print(f"\n{bad}/{len(files)} files outside target")
        else:
            print(f"\n✅ all {len(files)} files within target")

    if bad and len(files) > 0:
        logger.warn(TOOL_ID, f"{bad}/{len(files)} outside length target")
        return 1
    logger.done(TOOL_ID, f"all {len(files)} within target")
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
