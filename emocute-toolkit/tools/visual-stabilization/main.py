"""visual-stabilization — ffmpeg vidstab で手ブレ補正.

2 pass で vidstabdetect → vidstabtransform。アクション系録画素材の補正。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-stabilization"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual stabilization")
    p.add_argument("input")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--shakiness", type=int, default=5, help="1=低/10=高")
    p.add_argument("--smoothing", type=int, default=10)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    out = Path(args.out).expanduser().resolve()
    if not args.apply:
        print(f"[dry-run] {src.name} → {out.name}")
        print(f"  shakiness={args.shakiness} smoothing={args.smoothing}")
        return 0
    with tempfile.NamedTemporaryFile(suffix=".trf", delete=False) as t:
        trf = t.name
    p1 = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
          "-i", str(src),
          "-vf", f"vidstabdetect=shakiness={args.shakiness}:result={trf}",
          "-f", "null", "-"]
    r1 = subprocess.run(p1, capture_output=True, text=True, check=False)
    if r1.returncode != 0:
        logger.error(TOOL_ID, f"detect pass failed: {r1.stderr[-200:]}")
        return 3
    out.parent.mkdir(parents=True, exist_ok=True)
    p2 = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
          "-i", str(src),
          "-vf", f"vidstabtransform=input={trf}:smoothing={args.smoothing}",
          "-c:v", "libx264", "-crf", "18", "-c:a", "copy",
          str(out)]
    r2 = subprocess.run(p2, capture_output=True, text=True, check=False)
    Path(trf).unlink(missing_ok=True)
    if r2.returncode != 0:
        logger.error(TOOL_ID, f"transform pass failed: {r2.stderr[-200:]}")
        return 3
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"stabilized → {out.name}")
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
