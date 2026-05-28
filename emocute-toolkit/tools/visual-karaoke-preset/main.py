"""visual-karaoke-preset — SRT/LRC + 動画 → カラオケ風字幕焼き込み.

ass フィルタで色変化を時間制御。明朝/ゴシック preset 内蔵。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-karaoke-preset"

PRESETS = {
    "white_on_black": {"primary": "FFFFFF", "secondary": "888888", "outline": "000000"},
    "yellow_outline": {"primary": "FFFFFF", "secondary": "FFD700", "outline": "000000"},
    "pink_neon":      {"primary": "FFB6C1", "secondary": "FF1493", "outline": "1A0033"},
}


def srt_to_ass(srt: str, preset: dict, font: str, size: int) -> str:
    """SRT を ass スクリプトに変換（カラオケ機能は使わず単純焼込み）"""
    import re
    head = f"""[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},&H00{preset['primary']},&H00{preset['secondary']},&H00{preset['outline']},&H00000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    blocks = re.split(r"\n\n+", srt.strip())
    for blk in blocks:
        lines = blk.strip().splitlines()
        if len(lines) < 3:
            continue
        ts = re.search(r"(\d{2}):(\d{2}):(\d{2})[.,](\d+)\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d+)", lines[1])
        if not ts:
            continue
        def fmt(parts):
            h, m, s, ms = parts
            return f"{int(h)}:{int(m):02d}:{int(s):02d}.{int(ms[:2]):02d}"
        start = fmt(ts.groups()[:4])
        end = fmt(ts.groups()[4:])
        body = "\\N".join(lines[2:])
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{body}")
    return head + "\n".join(events) + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual karaoke-preset")
    p.add_argument("video")
    p.add_argument("--srt", required=True)
    p.add_argument("--preset", choices=list(PRESETS.keys()),
                   default="white_on_black")
    p.add_argument("--font", default="Hiragino Sans GB")
    p.add_argument("--size", type=int, default=48)
    p.add_argument("-o", "--out")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.video).expanduser().resolve()
    srt = Path(args.srt).expanduser().resolve()
    if not inp.exists() or not srt.exists():
        logger.error(TOOL_ID, f"missing: {inp} or {srt}")
        return 2
    out = Path(args.out).expanduser().resolve() if args.out \
        else inp.with_name(f"{inp.stem}_karaoke{inp.suffix}")
    ass_path = inp.with_suffix(".ass")
    ass_text = srt_to_ass(srt.read_text(errors="ignore"),
                          PRESETS[args.preset], args.font, args.size)
    ass_path.write_text(ass_text)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", str(inp),
           "-vf", f"ass={ass_path}",
           "-c:v", "libx264", "-crf", "18", "-c:a", "copy", str(out)]
    if not args.apply:
        print(f"[dry-run] {inp.name} + {srt.name} → {out.name}")
        ass_path.unlink(missing_ok=True)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    ass_path.unlink(missing_ok=True)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-300:]}")
        return 3
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"karaoke -> {out.name}")
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
