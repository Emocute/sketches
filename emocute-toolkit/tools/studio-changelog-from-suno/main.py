"""studio-changelog-from-suno — Suno セッションログから楽曲別 CHANGELOG を生成.

`Studio/sessions/<date>/log.jsonl` の各 song_id を解析、prompt 変更履歴・
ステム差替え・LANDR pass などのイベントを CHANGELOG.md にレンダリング。
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-changelog-from-suno"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio changelog-from-suno")
    p.add_argument("session_log", help="JSONL session log")
    p.add_argument("--song-id", help="特定の song_id のみ")
    p.add_argument("--out")
    return p


def run(args: argparse.Namespace) -> int:
    path = Path(args.session_log).expanduser().resolve()
    if not path.exists():
        logger.error(TOOL_ID, f"not found: {path}")
        return 2
    events: dict[str, list[dict]] = defaultdict(list)
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = e.get("song_id") or e.get("track_id") or "(unknown)"
        if args.song_id and sid != args.song_id:
            continue
        events[sid].append(e)

    out = []
    for sid, ev in events.items():
        out.append(f"## {sid}")
        for e in ev:
            ts = e.get("ts", "?")
            t = e.get("type", e.get("action", "?"))
            note = e.get("note") or e.get("prompt", "")
            out.append(f"- {ts}  [{t}]  {str(note)[:120]}")
        out.append("")
    md = "\n".join(out) or "(no events)"
    if args.out:
        p = Path(args.out).expanduser().resolve()
        p.write_text(md)
        print(f"✅ wrote {p}")
    else:
        print(md)
    logger.done(TOOL_ID, f"{sum(len(v) for v in events.values())} events for {len(events)} songs")
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
