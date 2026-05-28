"""studio-suno-style-catalog — Suno スタイルプロンプト辞書.

過去の楽曲ごとに使った style prompt を集約、ジャンル別タグでカテゴリ化。
新規楽曲制作時のプロンプト参照源。実音源 verify 必須
(`groove_verify_by_ear` 準拠で UI 信用しない)。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-suno-style-catalog"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio suno-style-catalog")
    p.add_argument("session_dir", help="Studio/sessions/")
    p.add_argument("--tag", help="特定タグでフィルタ")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.session_dir).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    catalog: dict[str, list[dict]] = {}
    for jl in root.rglob("*.jsonl"):
        for line in jl.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            style = e.get("style") or e.get("style_prompt")
            if not style:
                continue
            tags = e.get("tags") or []
            song = e.get("song_id") or jl.parent.name
            if args.tag and args.tag not in tags:
                continue
            for t in tags or ["(untagged)"]:
                catalog.setdefault(t, []).append({"song": song, "style": style[:80]})
    if args.json:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
    else:
        for tag, items in catalog.items():
            print(f"\n[{tag}] ({len(items)})")
            for it in items[:8]:
                print(f"  {it['song'][:24]:<24s}  {it['style']}")
            if len(items) > 8:
                print(f"  ... ({len(items) - 8} more)")
    logger.done(TOOL_ID, f"catalog: {sum(len(v) for v in catalog.values())} entries, {len(catalog)} tags")
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
