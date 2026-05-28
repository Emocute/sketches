"""sale-calendar-auto-post — X 投稿スケジュールの calendar 化.

JSONL の投稿スケジュールを iCalendar (.ics) に変換、Google/Apple Calendar に
import。手動投稿運用なので「リマインダー」として機能する。
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-calendar-auto-post"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale calendar-auto-post")
    p.add_argument("schedule_jsonl", help="{datetime, content} の JSONL")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--apply", action="store_true")
    return p


def to_ical_ts(s: str) -> str:
    t = dt.datetime.fromisoformat(s)
    return t.strftime("%Y%m%dT%H%M%S")


def run(args: argparse.Namespace) -> int:
    src = Path(args.schedule_jsonl).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    events = []
    for line in src.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    print(f"events: {len(events)}")
    if not args.apply:
        for e in events[:8]:
            print(f"  • {e.get('datetime','?')}  {e.get('content','')[:60]}")
        if len(events) > 8:
            print(f"  ... ({len(events) - 8} more)")
        print("\n[dry-run]")
        return 0
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//emocute//toolkit//EN"]
    for i, e in enumerate(events):
        try:
            ts = to_ical_ts(e["datetime"])
        except Exception:
            continue
        title = (e.get("content", "") or "")[:80].replace("\n", " ")
        ics += [
            "BEGIN:VEVENT",
            f"UID:emocute-{i}-{ts}@toolkit",
            f"DTSTART:{ts}",
            f"DTEND:{ts}",
            f"SUMMARY:📮 X post: {title}",
            f"DESCRIPTION:{e.get('content','')}",
            "END:VEVENT",
        ]
    ics.append("END:VCALENDAR")
    out.write_text("\n".join(ics))
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"ics {len(events)} events")
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
