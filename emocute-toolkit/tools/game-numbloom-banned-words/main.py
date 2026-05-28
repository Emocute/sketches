"""game-numbloom-banned-words — Numbloom テキスト内禁止語スキャン.

カード名・ダイアログ・人格名で MBTI/第三者 IP/絵文字（戦闘描写）等の検出。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-numbloom-banned-words"

# Numbloom 固有の禁則（CLAUDE.md より）
BANNED = [
    # MBTI / 16P
    (r"\b(I|E)(N|S)(T|F)(J|P)\b", "mbti_4letter"),
    (r"\b16Personalities\b", "16p"),
    # 戦闘描写での絵文字（feedback_combat_visual_direction より）
    # → 絵文字検出は別ツール
    # 第三者ゲーム由来名
    (r"\bStickerbush\b", "third_party_bgm"),
    (r"\bHollow Knight\b", "third_party_game"),
    (r"\bDKC2?\b", "third_party_game"),
    # 西日本方言（feedback_japanese_style）
    (r"せやな", "kansai"), (r"ちゃうやろ", "kansai"),
]

SCAN_EXTS = {".md", ".html", ".js", ".ts", ".json"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game numbloom-banned-words")
    p.add_argument("path", help="Numbloom dir or game.html")
    return p


def run(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        logger.error(TOOL_ID, f"not found: {target}")
        return 2
    files = [target] if target.is_file() else [
        f for f in target.rglob("*")
        if f.is_file() and f.suffix.lower() in SCAN_EXTS
        and "_archive" not in f.parts and ".git" not in f.parts
    ]
    hits = []
    for f in files:
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for pat_str, label in BANNED:
            pat = re.compile(pat_str)
            for m in pat.finditer(text):
                line = text[:m.start()].count("\n") + 1
                hits.append({"file": f.name, "type": label, "value": m.group(0), "line": line})
    if hits:
        print(f"❌ {len(hits)} banned-word hits")
        for h in hits[:30]:
            print(f"  [{h['type']}] {h['file'][:30]}:{h['line']}  '{h['value']}'")
        logger.warn(TOOL_ID, f"{len(hits)} banned-word hits")
        return 1
    print(f"✅ no banned words ({len(files)} files)")
    logger.done(TOOL_ID, f"clean {len(files)} files")
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
