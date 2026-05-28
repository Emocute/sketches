"""studio-production-phase-fsm — 楽曲制作フェーズの状態機械.

各 song の状態を idea → sketch → arranged → mastered → released で管理。
不正遷移 (mastered → sketch 等) を弾く。状態は YAML/JSON で保持。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-production-phase-fsm"

VALID_TRANSITIONS = {
    "idea":     {"sketch"},
    "sketch":   {"arranged", "idea"},
    "arranged": {"mastered", "sketch"},
    "mastered": {"released", "arranged"},
    "released": {"archived"},
    "archived": set(),
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio production-phase-fsm")
    p.add_argument("state_file", help="JSON: {song_id: phase}")
    sub = p.add_subparsers(dest="cmd", required=True)
    s_set = sub.add_parser("transition")
    s_set.add_argument("song_id")
    s_set.add_argument("to_phase")
    s_set.add_argument("--apply", action="store_true")
    s_show = sub.add_parser("show")
    s_show.add_argument("--phase", help="特定 phase でフィルタ")
    return p


def run(args: argparse.Namespace) -> int:
    sf = Path(args.state_file).expanduser().resolve()
    if not sf.exists():
        state = {}
    else:
        state = json.loads(sf.read_text())
    if args.cmd == "show":
        if args.phase:
            state = {k: v for k, v in state.items() if v == args.phase}
        for k, v in state.items():
            print(f"  {k:<28s}  {v}")
        print(f"\n{len(state)} songs")
        return 0
    cur = state.get(args.song_id, "idea")
    allowed = VALID_TRANSITIONS.get(cur, set())
    if args.to_phase not in allowed:
        logger.error(TOOL_ID, f"invalid transition: {cur} → {args.to_phase} (allowed: {sorted(allowed)})")
        return 1
    print(f"{args.song_id}: {cur} → {args.to_phase}")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    state[args.song_id] = args.to_phase
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(f"✅ state updated → {sf}")
    logger.done(TOOL_ID, f"{args.song_id}: {cur} → {args.to_phase}")
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
