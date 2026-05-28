"""visual-overlay-batch — 動画にロゴ/字幕/ウォーターマーク overlay を一括適用.

ffmpeg overlay フィルタで位置・透明度・タイミング指定。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-overlay-batch"

POSITIONS = {
    "tl": "10:10",
    "tr": "main_w-overlay_w-10:10",
    "bl": "10:main_h-overlay_h-10",
    "br": "main_w-overlay_w-10:main_h-overlay_h-10",
    "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual overlay-batch")
    p.add_argument("inputs", nargs="+", help="動画 (glob OK)")
    p.add_argument("--overlay", required=True, help="overlay PNG/MOV")
    p.add_argument("--position", choices=list(POSITIONS.keys()), default="br")
    p.add_argument("--opacity", type=float, default=1.0)
    p.add_argument("--start", type=float, default=0.0, help="overlay 開始秒")
    p.add_argument("--end", type=float, help="overlay 終了秒（省略=最後まで）")
    p.add_argument("--suffix", default="_ov", help="出力ファイル名 suffix")
    p.add_argument("--apply", action="store_true")
    return p


def build_filter(overlay_path: Path, pos: str, opacity: float,
                 start: float, end: float | None) -> str:
    pos_expr = POSITIONS[pos]
    # opacity via colorchannelmixer aa
    ov = f"[1:v]format=rgba,colorchannelmixer=aa={opacity}[ov];"
    enable = f"between(t,{start},{end})" if end else f"gte(t,{start})"
    return ov + f"[0:v][ov]overlay={pos_expr}:enable='{enable}'"


def process(inp: Path, overlay: Path, vf: str, suffix: str, apply: bool) -> int:
    out = inp.with_name(f"{inp.stem}{suffix}{inp.suffix}")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", str(inp), "-i", str(overlay),
           "-filter_complex", vf,
           "-c:v", "libx264", "-crf", "18", "-c:a", "copy", str(out)]
    if not apply:
        print(f"  [dry-run] {inp.name} → {out.name}")
        return 0
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        print(f"  ❌ {inp.name}: {r.stderr[-200:]}")
        return 1
    print(f"  ✅ {out.name}")
    return 0


def run(args: argparse.Namespace) -> int:
    overlay = Path(args.overlay).expanduser().resolve()
    if not overlay.exists():
        logger.error(TOOL_ID, f"overlay not found: {overlay}")
        return 2
    inputs = []
    for x in args.inputs:
        p = Path(x).expanduser()
        if "*" in x:
            inputs += list(p.parent.glob(p.name))
        else:
            inputs.append(p.resolve())
    inputs = [p for p in inputs if p.exists()]
    if not inputs:
        logger.error(TOOL_ID, "no valid inputs")
        return 2

    vf = build_filter(overlay, args.position, args.opacity, args.start, args.end)
    print(f"overlay: {overlay.name}  pos: {args.position}  α: {args.opacity}")
    print(f"applying to {len(inputs)} files")
    fail = 0
    for inp in inputs:
        if process(inp, overlay, vf, args.suffix, args.apply) != 0:
            fail += 1
    if not args.apply:
        print(f"\nuse --apply (would process {len(inputs)} files)")
    logger.done(TOOL_ID, f"overlay {len(inputs) - fail}/{len(inputs)} ok")
    return 0 if fail == 0 else 1


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
