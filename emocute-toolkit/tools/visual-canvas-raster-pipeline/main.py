"""visual-canvas-raster-pipeline — Canvas → ラスタライズ → MP4 の薄いパイプ.

`visual-canvas-png-seq` と組み合わせる pipeline 仕様。canvas を puppeteer で
連番 PNG にして、PNG seq tool で MP4 化、で終わるという三段の plan を提示。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-canvas-raster-pipeline"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual canvas-raster-pipeline")
    p.add_argument("html", help="canvas 入り HTML")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--frames", type=int, default=600)
    p.add_argument("--fps", type=int, default=60)
    p.add_argument("--workdir", default="raster_workdir")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.html).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"html not found: {src}")
        return 2
    out = Path(args.out).expanduser().resolve()
    workdir = Path(args.workdir).expanduser().resolve()
    print(f"HTML:    {src}")
    print(f"frames:  {args.frames} @ {args.fps}fps  → {args.frames/args.fps:.1f}s")
    print(f"workdir: {workdir}")
    print(f"out:     {out}")
    print("\nplan:")
    print(f"  1) puppeteer で {src.name} を {args.frames} フレーム連番 PNG 化 → {workdir}/")
    print(f"  2) visual-canvas-png-seq '{workdir}/frame_%%04d.png' -o {out} --fps {args.fps} --apply")
    print("\n[plan only] puppeteer 実装は別途必要")
    logger.done(TOOL_ID, f"plan: {src.name} → {out.name}")
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
