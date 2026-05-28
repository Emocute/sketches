"""visual-lrc-srt-json — 歌詞/字幕フォーマット相互変換.

LRC ↔ SRT ↔ JSON 双方向。MV 制作で歌詞同期に多用。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-lrc-srt-json"

LRC_TS = re.compile(r"\[(\d+):(\d+)(?:\.(\d+))?\]")
SRT_TS = re.compile(r"(\d{2}):(\d{2}):(\d{2})[.,](\d+)")


def lrc_parse(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        stamps = LRC_TS.findall(line)
        body = LRC_TS.sub("", line).strip()
        if not body or not stamps:
            continue
        for m_, s_, ms_ in stamps:
            t = int(m_) * 60 + int(s_) + (int((ms_ or "0").ljust(3, "0")[:3])/1000)
            out.append({"start": round(t, 3), "text": body})
    out.sort(key=lambda x: x["start"])
    # end は次の start
    for i, seg in enumerate(out):
        seg["end"] = out[i + 1]["start"] if i + 1 < len(out) else seg["start"] + 4
    return out


def srt_parse(text: str) -> list[dict]:
    out = []
    blocks = re.split(r"\n\n+", text.strip())
    for blk in blocks:
        lines = blk.strip().splitlines()
        if len(lines) < 3:
            continue
        ts = re.search(r"(\d{2}:\d{2}:\d{2}[.,]\d+)\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d+)", lines[1])
        if not ts:
            continue
        def conv(t: str) -> float:
            m_ = SRT_TS.match(t)
            return int(m_.group(1)) * 3600 + int(m_.group(2)) * 60 + int(m_.group(3)) + int(m_.group(4)) / 1000
        body = "\n".join(lines[2:])
        out.append({"start": conv(ts.group(1)), "end": conv(ts.group(2)), "text": body})
    return out


def to_srt(segs: list[dict]) -> str:
    def fmt(t: float) -> str:
        ms = int((t - int(t)) * 1000); t_int = int(t)
        h, t_int = divmod(t_int, 3600); m_, s_ = divmod(t_int, 60)
        return f"{h:02d}:{m_:02d}:{s_:02d},{ms:03d}"
    out = []
    for i, s in enumerate(segs, 1):
        out.append(f"{i}\n{fmt(s['start'])} --> {fmt(s['end'])}\n{s['text']}\n")
    return "\n".join(out)


def to_lrc(segs: list[dict]) -> str:
    out = []
    for s in segs:
        t = s["start"]; m_ = int(t // 60); rest = t - m_ * 60
        out.append(f"[{m_:02d}:{rest:05.2f}]{s['text']}")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual lrc-srt-json")
    p.add_argument("input")
    p.add_argument("--to", choices=["srt", "lrc", "json"], required=True)
    p.add_argument("-o", "--out")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    text = inp.read_text(errors="ignore")
    if inp.suffix.lower() == ".lrc":
        segs = lrc_parse(text)
    elif inp.suffix.lower() == ".srt":
        segs = srt_parse(text)
    elif inp.suffix.lower() == ".json":
        segs = json.loads(text)
    else:
        logger.error(TOOL_ID, "unknown ext")
        return 2

    out_ext = {"srt": ".srt", "lrc": ".lrc", "json": ".json"}[args.to]
    out = Path(args.out).expanduser().resolve() if args.out \
        else inp.with_suffix(out_ext)
    if args.to == "srt":
        out.write_text(to_srt(segs))
    elif args.to == "lrc":
        out.write_text(to_lrc(segs))
    else:
        out.write_text(json.dumps(segs, ensure_ascii=False, indent=2))
    print(f"✅ {len(segs)} segs → {out}")
    logger.done(TOOL_ID, f"{inp.suffix} -> {args.to}: {len(segs)} segs")
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
