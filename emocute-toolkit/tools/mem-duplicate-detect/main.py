"""mem-duplicate-detect — memory ファイル間の重複検出.

description/name フィールドが類似、本文 trigram Jaccard が高いものを並べる。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "mem-duplicate-detect"
MEMORY_DIR = Path.home() / ".claude/projects/-Users-emocute-Downloads/memory"


def trigrams(s: str) -> set[str]:
    s = re.sub(r"\s+", " ", s).strip()
    return {s[i:i+3] for i in range(len(s) - 2)} if len(s) >= 3 else set()


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0
    return len(a & b) / len(a | b)


def extract_meta(text: str) -> dict:
    out = {"name": "", "description": "", "type": ""}
    in_fm = False
    for line in text.splitlines():
        if line.strip() == "---":
            if in_fm:
                break
            in_fm = True
            continue
        if in_fm:
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                if k in out:
                    out[k] = v.strip()
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute mem duplicate-detect")
    p.add_argument("--memory-dir", default=str(MEMORY_DIR))
    p.add_argument("--threshold", type=float, default=0.4,
                   help="Jaccard threshold (default 0.4)")
    return p


def run(args: argparse.Namespace) -> int:
    d = Path(args.memory_dir).expanduser().resolve()
    files = [f for f in d.glob("*.md") if f.name != "MEMORY.md"]
    docs = []
    for f in files:
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        body = text.split("---", 2)[-1] if "---" in text else text
        docs.append({"file": f.name, "meta": extract_meta(text),
                     "tri": trigrams(body[:2000])})

    pairs = []
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            sim = jaccard(docs[i]["tri"], docs[j]["tri"])
            if sim >= args.threshold:
                pairs.append({"a": docs[i]["file"], "b": docs[j]["file"], "sim": sim})

    pairs.sort(key=lambda x: -x["sim"])
    if pairs:
        print(f"{len(pairs)} potentially-duplicate pairs (≥{args.threshold})")
        for p in pairs[:30]:
            print(f"  {p['sim']:.2f}  {p['a']}  <→  {p['b']}")
        logger.warn(TOOL_ID, f"{len(pairs)} dup pairs")
        return 1
    print(f"✅ no duplicates above {args.threshold}")
    logger.done(TOOL_ID, "no dup")
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
