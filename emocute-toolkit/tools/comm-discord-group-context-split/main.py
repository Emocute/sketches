"""comm-discord-group-context-split — Discord グループ別 context 分割.

DM 履歴 / グループチャット履歴を chat_id ごとに分割し、`<chat_id>/<date>.md` に
保存。`feedback_arata_dm_terminal_only` 準拠で DM は別管理。
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "comm-discord-group-context-split"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute comm discord-group-context-split")
    p.add_argument("messages_jsonl", help="fetch 済 messages JSONL")
    p.add_argument("--out-dir", default="_drafts/discord_split")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.messages_jsonl).expanduser().resolve()
    if not src.exists():
        logger.error(TOOL_ID, f"not found: {src}")
        return 2
    buckets: dict[str, list[dict]] = defaultdict(list)
    for line in src.read_text(errors="ignore").splitlines():
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        cid = m.get("chat_id") or m.get("channel_id") or "unknown"
        buckets[cid].append(m)
    print(f"groups: {len(buckets)}")
    for cid, msgs in buckets.items():
        print(f"  {cid}: {len(msgs)} messages")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    out = Path(args.out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    for cid, msgs in buckets.items():
        chat_dir = out / str(cid)
        chat_dir.mkdir(exist_ok=True)
        body = "\n".join(f"- {m.get('ts','?')}  {m.get('user','?')}: {m.get('content','')[:200]}" for m in msgs)
        (chat_dir / "all.md").write_text(f"# chat {cid}\n\n{body}\n")
    print(f"✅ split into {len(buckets)} group dirs")
    logger.done(TOOL_ID, f"discord split: {len(buckets)}")
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
