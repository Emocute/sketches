"""studio-credit-tracker — アルバムのクレジット情報を集約・正規化.

各楽曲の ID3 タグ + manifest.yaml から、作曲/作詞/編曲/演奏/MIX/マスタリング
を集約し、liner notes 用 markdown を吐く。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-credit-tracker"

DEFAULT_ROLES = ["composer", "lyricist", "arranger", "performer",
                 "engineer", "mix", "master", "vocals"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio credit-tracker")
    p.add_argument("album_dir")
    p.add_argument("--manifest", help="YAML credits manifest")
    p.add_argument("--out", help="出力 md path")
    p.add_argument("--json", action="store_true")
    return p


def collect_from_id3(album_dir: Path) -> list[dict]:
    try:
        from mutagen import File as MFile
    except ImportError:
        return []
    rows = []
    for f in sorted(album_dir.glob("*.mp3")):
        m = MFile(f, easy=True)
        if m is None:
            continue
        rows.append({
            "track": f.stem,
            "artist": (m.get("artist") or ["?"])[0],
            "title": (m.get("title") or [f.stem])[0],
            "composer": (m.get("composer") or ["Emocute"])[0],
        })
    return rows


def load_manifest(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        return {}
    return yaml.safe_load(path.read_text()) or {}


def render_md(album_dir: Path, tracks: list[dict], manifest: dict) -> str:
    album = manifest.get("album", album_dir.name)
    out = [f"# {album} — Credits\n"]
    for i, t in enumerate(tracks, 1):
        out.append(f"## {i:02d}. {t['title']}\n")
        for role in DEFAULT_ROLES:
            val = manifest.get("tracks", {}).get(t["track"], {}).get(role) or t.get(role)
            if val:
                out.append(f"- **{role}**: {val}")
        out.append("")
    out.append("---")
    out.append(f"\nProduced by Emocute Lab.")
    return "\n".join(out)


def run(args: argparse.Namespace) -> int:
    d = Path(args.album_dir).expanduser().resolve()
    if not d.is_dir():
        logger.error(TOOL_ID, f"not dir: {d}")
        return 2
    tracks = collect_from_id3(d)
    manifest = load_manifest(Path(args.manifest).expanduser().resolve()) \
        if args.manifest else {}
    if args.json:
        print(json.dumps({"tracks": tracks, "manifest": manifest},
                         ensure_ascii=False, indent=2))
    else:
        md = render_md(d, tracks, manifest)
        if args.out:
            out = Path(args.out).expanduser().resolve()
            out.write_text(md)
            print(f"✅ wrote {out}")
        else:
            print(md)
    logger.done(TOOL_ID, f"credits for {len(tracks)} tracks")
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
