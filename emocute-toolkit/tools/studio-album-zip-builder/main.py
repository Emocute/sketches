"""studio-album-zip-builder — LICENSE/README/ジャケ統合 ZIP.

album_dir 内の audio + cover + 自動生成 LICENSE.md + README.md を ZIP 化。
LICENSE は Emocute Lab. ブランド規約 (Copyright Emocute Lab. + support@emocutelab.com)。
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-album-zip-builder"

LICENSE_TEMPLATE = """# LICENSE

Copyright (c) {year} Emocute Lab. All rights reserved.

This album and all included audio files are licensed for personal listening only.

NOT permitted without prior written permission:
- Commercial use, public broadcast, or resale of the audio
- Redistribution of the original files
- Use in derivative works (remixes, samples, video soundtracks)

Contact: support@emocutelab.com
"""

README_TEMPLATE = """# {album_name}

by Emocute — {year}

## Tracks

{track_list}

## Files

- `/audio/` — Tracks ({audio_format})
- `/cover/` — Album artwork
- `LICENSE.md` — License terms
- `VERSION` — Album version

## Support

support@emocutelab.com
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio album-zip-builder")
    p.add_argument("album_dir", help="アルバムの素材ディレクトリ (audio/* + cover.{jpg,png})")
    p.add_argument("--name", required=True, help="アルバム名（ZIP 名と README に使用）")
    p.add_argument("--version", default="1.0.0")
    p.add_argument("--out", help="出力 ZIP パス (default: album_dir/../<name>_v<ver>.zip)")
    p.add_argument("--apply", action="store_true")
    return p


def collect_tracks(album_dir: Path) -> list[Path]:
    audio = []
    for ext in (".mp3", ".wav", ".flac", ".m4a"):
        audio.extend(sorted(album_dir.rglob(f"*{ext}")))
    # 重複除外 (audio/ ディレクトリ優先)
    seen = set()
    out = []
    for p in audio:
        if p.stem in seen:
            continue
        seen.add(p.stem)
        out.append(p)
    return out


def find_cover(album_dir: Path) -> Path | None:
    for name in ("cover.jpg", "cover.png", "cover.jpeg", "front.jpg"):
        p = album_dir / name
        if p.exists():
            return p
    for p in album_dir.glob("*.jpg"):
        if "cover" in p.name.lower():
            return p
    return None


def run(args: argparse.Namespace) -> int:
    album_dir = Path(args.album_dir).expanduser().resolve()
    if not album_dir.is_dir():
        logger.error(TOOL_ID, f"not a directory: {album_dir}")
        return 2

    tracks = collect_tracks(album_dir)
    cover = find_cover(album_dir)
    year = dt.date.today().year

    if not tracks:
        logger.error(TOOL_ID, "no audio files found")
        return 1

    audio_format = ", ".join(sorted({p.suffix.lstrip('.').upper() for p in tracks}))
    track_list = "\n".join(f"{i+1}. {p.stem}" for i, p in enumerate(tracks))
    readme = README_TEMPLATE.format(
        album_name=args.name, year=year,
        track_list=track_list, audio_format=audio_format,
    )
    license_text = LICENSE_TEMPLATE.format(year=year)
    version_text = args.version

    out_zip = Path(args.out).expanduser().resolve() if args.out \
        else album_dir.parent / f"{args.name}_v{args.version}.zip"

    print(f"album: {args.name} v{args.version}")
    print(f"tracks: {len(tracks)}")
    print(f"cover: {cover.name if cover else '(none)'}")
    print(f"out: {out_zip}")
    if not args.apply:
        print("\n[dry-run] use --apply to build")
        return 0

    if out_zip.exists():
        logger.error(TOOL_ID, f"output exists, refusing overwrite: {out_zip}")
        print("❌ refusing to overwrite existing ZIP")
        return 1

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in tracks:
            zf.write(p, arcname=f"audio/{p.name}")
        if cover:
            zf.write(cover, arcname=f"cover/{cover.name}")
        zf.writestr("LICENSE.md", license_text)
        zf.writestr("README.md", readme)
        zf.writestr("VERSION", version_text)

    size_mb = out_zip.stat().st_size / 1e6
    print(f"\n✅ built: {out_zip}  ({size_mb:.1f} MB)")
    logger.done(TOOL_ID, f"built {out_zip.name} ({size_mb:.1f}MB)")
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
