"""visual-ffprobe-verify — 動画の解像度/fps/duration/コーデック検証.

書出し動画が想定どおりか dashboard 風にレポート。
4K/1080p/縦 1080x1920 等の preset との偏差を表示。
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-ffprobe-verify"

PRESETS = {
    "1080p": (1920, 1080, 30),
    "1080p60": (1920, 1080, 60),
    "4k": (3840, 2160, 30),
    "vertical": (1080, 1920, 30),
    "square": (1080, 1080, 30),
    "x_premium": (1920, 1080, 30),
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual ffprobe-verify")
    p.add_argument("path")
    p.add_argument("--preset", choices=list(PRESETS.keys()))
    p.add_argument("--json", action="store_true")
    return p


def probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        return {}
    return json.loads(r.stdout)


def fmt_one(path: Path, preset: tuple[int, int, int] | None) -> dict:
    info = probe(path)
    if not info:
        return {"file": path.name, "error": "ffprobe failed"}
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    w = int(video.get("width", 0))
    h = int(video.get("height", 0))
    fps_str = video.get("r_frame_rate", "0/1")
    n, d = fps_str.split("/")
    fps = round(int(n) / int(d), 2) if int(d) > 0 else 0
    duration = float(info.get("format", {}).get("duration", 0))
    out = {
        "file": path.name,
        "width": w, "height": h, "fps": fps,
        "duration_s": round(duration, 2),
        "video_codec": video.get("codec_name", ""),
        "audio_codec": audio.get("codec_name", ""),
        "size_mb": round(int(info.get("format", {}).get("size", 0)) / 1e6, 1),
        "odd_dimensions": (w % 2 != 0) or (h % 2 != 0),
    }
    if preset:
        ew, eh, efps = preset
        out["preset_match"] = (w == ew and h == eh)
        out["fps_diff"] = round(fps - efps, 2)
    return out


def run(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        logger.error(TOOL_ID, f"not found: {target}")
        return 2
    files = [target] if target.is_file() else [
        p for p in target.rglob("*")
        if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}
    ]
    preset = PRESETS.get(args.preset) if args.preset else None
    rows = [fmt_one(p, preset) for p in files]

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'file':<30} {'res':<11} {'fps':>5} {'dur':>7} {'codec':<8} {'flags'}")
        print("-" * 80)
        for r in rows:
            if "error" in r:
                print(f"  {r['file']:<28}  ERR")
                continue
            flags = []
            if r["odd_dimensions"]:
                flags.append("⚠️odd")
            if preset and not r.get("preset_match"):
                flags.append("⚠️preset")
            print(f"{r['file'][:28]:<30} "
                  f"{r['width']}x{r['height']:<5} "
                  f"{r['fps']:>5} "
                  f"{r['duration_s']:>7.1f} "
                  f"{r['video_codec']:<8} "
                  f"{' '.join(flags)}")

    bad = sum(1 for r in rows if r.get("odd_dimensions") or (preset and not r.get("preset_match", True)))
    if bad:
        logger.warn(TOOL_ID, f"{bad}/{len(rows)} files violate spec")
        return 1
    logger.done(TOOL_ID, f"verified {len(rows)} files")
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
