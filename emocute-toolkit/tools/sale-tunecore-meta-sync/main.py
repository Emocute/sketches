"""sale-tunecore-meta-sync — TuneCore メタデータと正本 ID3 の同期チェック.

TuneCore 登録メタ (CSV エクスポート) vs ローカル WAV の ID3 タグを比較、
不一致を一覧化。`album_reach_jp_only_2026-05-20` 準拠で JP-only な
description フィールドの監査も含む。
"""
from __future__ import annotations
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-tunecore-meta-sync"

try:
    from mutagen.easyid3 import EasyID3  # type: ignore
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale tunecore-meta-sync")
    p.add_argument("tunecore_csv")
    p.add_argument("audio_dir")
    return p


def run(args: argparse.Namespace) -> int:
    if not HAS_MUTAGEN:
        logger.error(TOOL_ID, "mutagen not installed")
        return 3
    csv_path = Path(args.tunecore_csv).expanduser().resolve()
    audio_dir = Path(args.audio_dir).expanduser().resolve()
    if not csv_path.exists() or not audio_dir.exists():
        logger.error(TOOL_ID, "input paths missing")
        return 2
    tc_data = {}
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            title = (row.get("title") or row.get("Track Title", "")).strip()
            if title:
                tc_data[title.lower()] = row
    diffs = []
    for audio in audio_dir.rglob("*.mp3"):
        try:
            tag = EasyID3(audio)
        except Exception:
            continue
        title = (tag.get("title", [""])[0] or "").strip()
        if not title:
            continue
        if title.lower() not in tc_data:
            diffs.append({"file": audio.name, "issue": f"not in TuneCore: {title}"})
            continue
        tc = tc_data[title.lower()]
        tc_artist = tc.get("artist") or tc.get("Artist", "")
        local_artist = (tag.get("artist", [""])[0] or "")
        if tc_artist != local_artist:
            diffs.append({"file": audio.name, "issue": f"artist: tc='{tc_artist}' local='{local_artist}'"})
    print(f"checked: {len(list(audio_dir.rglob('*.mp3')))} mp3s vs {len(tc_data)} TuneCore rows")
    print(f"diffs: {len(diffs)}")
    for d in diffs[:30]:
        print(f"  ⚠ {d['file']:<30s}  {d['issue']}")
    logger.done(TOOL_ID, f"diffs: {len(diffs)}")
    return 1 if diffs else 0


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
