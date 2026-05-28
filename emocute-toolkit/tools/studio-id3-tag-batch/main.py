"""studio-id3-tag-batch — ID3 タグ一括更新.

album, artist, year, genre, cover image を csv/yaml から一括適用。
mutagen 依存。Emocute Lab. ブランド規約と整合（artist=Emocute）。
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-id3-tag-batch"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio id3-tag-batch")
    p.add_argument("audio_dir", help="MP3 ディレクトリ")
    p.add_argument("--artist", default="Emocute")
    p.add_argument("--album", required=False)
    p.add_argument("--year", required=False)
    p.add_argument("--genre", required=False)
    p.add_argument("--cover", help="cover JPG/PNG")
    p.add_argument("--mapping", help="csv: filename,title,track_no")
    p.add_argument("--apply", action="store_true")
    return p


def load_mapping(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with path.open() as f:
        for row in csv.DictReader(f):
            fname = row.get("filename") or row.get("file")
            if fname:
                out[fname] = row
    return out


def apply_tags(path: Path, args, mapping_row: dict | None,
               cover_bytes: bytes | None) -> bool:
    try:
        from mutagen.easyid3 import EasyID3
        from mutagen.id3 import APIC, ID3, ID3NoHeaderError
        from mutagen.mp3 import MP3
    except ImportError:
        raise RuntimeError("mutagen not installed (pip install mutagen)")

    try:
        audio = EasyID3(path)
    except ID3NoHeaderError:
        audio = MP3(path)
        audio.add_tags()
        audio = EasyID3(path)

    audio["artist"] = args.artist
    if args.album:
        audio["album"] = args.album
    if args.year:
        audio["date"] = args.year
    if args.genre:
        audio["genre"] = args.genre
    if mapping_row:
        if mapping_row.get("title"):
            audio["title"] = mapping_row["title"]
        if mapping_row.get("track_no"):
            audio["tracknumber"] = mapping_row["track_no"]
    audio.save()

    if cover_bytes:
        id3 = ID3(path)
        # delete existing APIC
        for k in list(id3.keys()):
            if k.startswith("APIC"):
                del id3[k]
        mime = "image/jpeg"
        suffix = Path(args.cover).suffix.lower() if args.cover else ".jpg"
        if suffix == ".png":
            mime = "image/png"
        id3.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover_bytes))
        id3.save()
    return True


def run(args: argparse.Namespace) -> int:
    audio_dir = Path(args.audio_dir).expanduser().resolve()
    if not audio_dir.is_dir():
        logger.error(TOOL_ID, f"not a directory: {audio_dir}")
        return 2

    mapping = load_mapping(Path(args.mapping)) if args.mapping else {}
    cover_bytes = None
    if args.cover:
        cover_path = Path(args.cover).expanduser().resolve()
        if cover_path.exists():
            cover_bytes = cover_path.read_bytes()

    files = sorted(audio_dir.glob("*.mp3"))
    print(f"{len(files)} mp3 files in {audio_dir}")
    print(f"  artist:  {args.artist}")
    print(f"  album:   {args.album or '(unchanged)'}")
    print(f"  year:    {args.year or '(unchanged)'}")
    print(f"  genre:   {args.genre or '(unchanged)'}")
    print(f"  cover:   {args.cover or '(no change)'}")
    print(f"  mapping: {args.mapping or '(none)'}")

    if not args.apply:
        print("\n[dry-run] use --apply to write tags")
        return 0

    n = 0
    for f in files:
        row = mapping.get(f.name)
        try:
            apply_tags(f, args, row, cover_bytes)
            n += 1
            print(f"  ✅ {f.name}")
        except Exception as e:
            print(f"  ❌ {f.name}: {e}")

    logger.done(TOOL_ID, f"tagged {n}/{len(files)}", meta={"album": args.album})
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
