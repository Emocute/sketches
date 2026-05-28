"""visual-deinterlace-auto — インターレース判定 → yadif 自動適用.

ffprobe で `field_order` を確認、interlaced なら yadif=1 で deinterlace。
旧素材アーカイブ流用時に必須。
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-deinterlace-auto"


def probe_field_order(path: Path) -> str:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    data = json.loads(r.stdout)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    return v.get("field_order", "unknown") if v else "unknown"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual deinterlace-auto")
    p.add_argument("input")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--force", action="store_true", help="検出を無視して yadif")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    field = probe_field_order(src)
    print(f"file:        {src.name}")
    print(f"field_order: {field}")
    interlaced = args.force or field in ("tt", "bb", "tb", "bt")
    print(f"action:      {'yadif=1' if interlaced else 'no-op (progressive)'}")
    if not interlaced:
        return 0
    out = Path(args.out).expanduser().resolve()
    if not args.apply:
        print("[dry-run]")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(src),
           "-vf", "yadif=1",
           "-c:v", "libx264", "-crf", "18", "-c:a", "copy",
           str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-200:]}")
        return 3
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"deinterlace → {out.name}")
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
