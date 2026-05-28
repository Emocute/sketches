"""audit-id3-completeness — MP3/WAV の ID3 タグ完備チェック.

artist=Emocute、album、title、track_no、year、cover が全部入っているか。
DSP 配信前の漏れ検出。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "audit-id3-completeness"

REQUIRED = ["artist", "album", "title", "tracknumber", "date"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute audit id3-completeness")
    p.add_argument("path", help="ファイル or ディレクトリ")
    p.add_argument("--expect-artist", default="Emocute")
    p.add_argument("--json", action="store_true")
    return p


def check_file(path: Path, expect_artist: str) -> dict:
    out = {"file": path.name, "missing": [], "wrong": []}
    try:
        from mutagen import File as MFile
        from mutagen.id3 import ID3, APIC
    except ImportError:
        out["error"] = "mutagen not installed"
        return out
    try:
        m = MFile(path, easy=True)
    except Exception as e:
        out["error"] = f"parse failed: {e}"
        return out
    if m is None:
        out["error"] = "unsupported format"
        return out
    for k in REQUIRED:
        v = m.get(k)
        if not v:
            out["missing"].append(k)
    artist = m.get("artist")
    if artist and artist[0] != expect_artist:
        out["wrong"].append(f"artist='{artist[0]}' (expect {expect_artist})")
    # Cover check (APIC frame on MP3)
    has_cover = False
    if path.suffix.lower() == ".mp3":
        try:
            id3 = ID3(path)
            has_cover = any(isinstance(f, APIC) for f in id3.values())
        except Exception:
            pass
    out["has_cover"] = has_cover
    return out


def run(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        logger.error(TOOL_ID, f"not found: {target}")
        return 2
    files = [target] if target.is_file() else [
        f for f in target.rglob("*")
        if f.is_file() and f.suffix.lower() in {".mp3", ".flac", ".m4a", ".wav"}
    ]
    rows = [check_file(f, args.expect_artist) for f in files]
    issues = [r for r in rows if r.get("missing") or r.get("wrong")
              or r.get("error") or not r.get("has_cover", True)]

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        print(f"checked {len(rows)} files, {len(issues)} have issues")
        for r in issues[:30]:
            parts = []
            if r.get("error"):
                parts.append(f"ERR: {r['error']}")
            if r.get("missing"):
                parts.append(f"missing: {','.join(r['missing'])}")
            if r.get("wrong"):
                parts.append(f"wrong: {','.join(r['wrong'])}")
            if r.get("has_cover") is False:
                parts.append("no cover")
            print(f"  {r['file'][:50]:<52} {' | '.join(parts)}")
    if issues:
        logger.warn(TOOL_ID, f"{len(issues)}/{len(rows)} files incomplete")
        return 1
    logger.done(TOOL_ID, f"{len(rows)} files complete")
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
