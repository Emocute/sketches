"""visual-ogp-generator — OGP 画像 (1200x630) を ffmpeg で生成.

下地画像 + テキスト overlay。Pillow 非依存（ffmpeg drawtext のみ）。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-ogp-generator"

DEFAULT_FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual ogp-generator")
    p.add_argument("--title", required=True)
    p.add_argument("--subtitle", default="")
    p.add_argument("--bg", help="背景画像 path (省略=単色)")
    p.add_argument("--bg-color", default="0x111111")
    p.add_argument("--text-color", default="white")
    p.add_argument("--font", default=DEFAULT_FONT)
    p.add_argument("--size", default="1200x630")
    p.add_argument("-o", "--out", required=True)
    return p


def run(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser().resolve()
    w, h = (int(x) for x in args.size.split("x"))
    font = Path(args.font)
    if not font.exists():
        logger.warn(TOOL_ID, f"font missing: {font}, fallback")
        font_path = ""
    else:
        font_path = f":fontfile='{font}'"

    # 背景: 画像 or 単色
    if args.bg:
        bg = Path(args.bg).expanduser().resolve()
        if not bg.exists():
            logger.error(TOOL_ID, f"bg not found: {bg}")
            return 2
        bg_input = ["-i", str(bg)]
        bg_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    else:
        bg_input = ["-f", "lavfi", "-i", f"color=c={args.bg_color}:s={w}x{h}:d=1"]
        bg_filter = "null"

    # drawtext: title 大、subtitle 小、垂直中央
    title_y = h // 2 - 60
    sub_y = h // 2 + 30
    title_size = max(40, w // 24)
    sub_size = max(24, w // 48)
    safe_title = args.title.replace("'", r"\'").replace(":", r"\:")
    drawtitle = (
        f"drawtext=text='{safe_title}'{font_path}"
        f":fontsize={title_size}:fontcolor={args.text_color}"
        f":x=(w-text_w)/2:y={title_y}"
    )
    flt = f"{bg_filter},{drawtitle}"
    if args.subtitle:
        safe_sub = args.subtitle.replace("'", r"\'").replace(":", r"\:")
        flt += (
            f",drawtext=text='{safe_sub}'{font_path}"
            f":fontsize={sub_size}:fontcolor={args.text_color}"
            f":x=(w-text_w)/2:y={sub_y}"
        )

    cmd = ["ffmpeg", "-y", "-hide_banner"] + bg_input + \
          ["-vf", flt, "-frames:v", "1", str(out)]
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"ffmpeg failed: {r.stderr[-400:]}")
        return 3
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"ogp -> {out.name}")
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
