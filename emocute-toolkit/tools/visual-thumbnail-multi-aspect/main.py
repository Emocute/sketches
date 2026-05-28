"""visual-thumbnail-multi-aspect — 動画 → 16:9 / 9:16 / 1:1 サムネ.

ffmpeg で指定秒のフレームを抜き、ImageMagick 非依存で aspect 別にクロップ生成。
OGP / X カード / Square / 縦動画サムネを 1 コマンド。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-thumbnail-multi-aspect"

ASPECTS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1":  (1080, 1080),
    "4:5":  (1080, 1350),
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual thumbnail-multi-aspect")
    p.add_argument("input")
    p.add_argument("--at", type=float, default=2.0, help="切出秒 (default 2.0s)")
    p.add_argument("--aspects", default="16:9,9:16,1:1",
                   help=f"csv from {list(ASPECTS.keys())}")
    p.add_argument("--out-dir", help="出力先 (default: input parent)")
    p.add_argument("--apply", action="store_true")
    return p


def gen_one(input_path: Path, at: float, aspect: str, out_path: Path) -> bool:
    w, h = ASPECTS[aspect]
    vf = (
        f"scale=w='if(gt(a,{w}/{h}),-2,{w})':h='if(gt(a,{w}/{h}),{h},-2)',"
        f"crop={w}:{h}"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", str(at), "-i", str(input_path),
        "-vframes", "1",
        "-vf", vf,
        "-q:v", "2",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, check=False)
    return r.returncode == 0


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    aspects = [a.strip() for a in args.aspects.split(",")]
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else inp.parent

    print(f"input: {inp.name}  at {args.at}s")
    print(f"aspects: {aspects}")

    if not args.apply:
        for a in aspects:
            fname = f"{inp.stem}_thumb_{a.replace(':', 'x')}.jpg"
            print(f"  would write: {out_dir / fname}")
        print("\n[dry-run] use --apply")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for a in aspects:
        out_path = out_dir / f"{inp.stem}_thumb_{a.replace(':', 'x')}.jpg"
        if gen_one(inp, args.at, a, out_path):
            print(f"  ✅ {out_path.name}")
            n += 1
        else:
            print(f"  ❌ {a} failed")
    logger.done(TOOL_ID, f"generated {n}/{len(aspects)} thumbs for {inp.name}")
    return 0 if n == len(aspects) else 1


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
