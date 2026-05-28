"""studio-sample-pack-builder — 30秒切出 → ZIP.

album_dir の各 track から先頭/中央/終盤の 30 秒ハイライトを切り出し、
sample pack ZIP を生成。プレビュー配布や Splice 風サンプルパック用。
"""
from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-sample-pack-builder"

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio sample-pack-builder")
    p.add_argument("source", help="audio source directory")
    p.add_argument("out_zip")
    p.add_argument("--length", type=float, default=30.0)
    p.add_argument("--mode", choices=["head", "middle", "all"], default="middle",
                   help="切出位置 (default middle)")
    p.add_argument("--apply", action="store_true")
    return p


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=False,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def extract_clip(src: Path, dst: Path, start: float, length: float) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-ss", str(start), "-t", str(length),
         "-i", str(src),
         "-c:a", "libmp3lame", "-q:a", "2",
         "-af", "afade=t=in:d=0.2,afade=t=out:st={}:d=0.5".format(max(0, length - 0.5)),
         str(dst)],
        capture_output=True, check=False,
    )
    return r.returncode == 0


def run(args: argparse.Namespace) -> int:
    src = Path(args.source).expanduser().resolve()
    if not src.is_dir():
        logger.error(TOOL_ID, f"not a dir: {src}")
        return 2
    out_zip = Path(args.out_zip).expanduser().resolve()

    files = sorted(p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS)
    if not files:
        logger.error(TOOL_ID, "no audio files")
        return 1

    print(f"src: {src}  ({len(files)} tracks)")
    print(f"length: {args.length}s  mode: {args.mode}")
    print(f"out: {out_zip}")

    if not args.apply:
        for f in files[:5]:
            dur = probe_duration(f)
            print(f"  preview: {f.name}  ({dur:.1f}s)")
        if len(files) > 5:
            print(f"  ... and {len(files) - 5} more")
        print("\n[dry-run] use --apply to build")
        return 0

    if out_zip.exists():
        logger.error(TOOL_ID, f"refusing to overwrite: {out_zip}")
        return 1
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        clips: list[Path] = []
        for f in files:
            dur = probe_duration(f)
            if dur <= 0:
                continue
            positions = []
            if args.mode == "head":
                positions = [0]
            elif args.mode == "middle":
                positions = [max(0, (dur - args.length) / 2)]
            else:  # all
                if dur > args.length * 3:
                    positions = [0, (dur - args.length) / 2, max(0, dur - args.length)]
                else:
                    positions = [0]
            for i, start in enumerate(positions):
                suffix = "" if len(positions) == 1 else f"_{['head','mid','tail'][i]}"
                out_clip = tdp / f"{f.stem}{suffix}_preview.mp3"
                if extract_clip(f, out_clip, start, args.length):
                    clips.append(out_clip)
        if not clips:
            logger.error(TOOL_ID, "no clips extracted")
            return 1
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for c in clips:
                zf.write(c, arcname=c.name)
            readme = (
                f"# Sample pack\n\n"
                f"{len(clips)} clips ({args.length}s each), source: {src.name}\n\n"
                f"by Emocute — see support@emocutelab.com\n"
            )
            zf.writestr("README.md", readme)

    size_mb = out_zip.stat().st_size / 1e6
    print(f"✅ built sample pack: {out_zip}  ({size_mb:.1f} MB, {len(files)} sources)")
    logger.done(TOOL_ID, f"sample pack {out_zip.name}", meta={"clips": len(files)})
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
