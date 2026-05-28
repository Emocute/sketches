"""visual-chrome-app-launch — Chrome --app= 録画ランチャ.

spec: registry/visual/visual-chrome-app-launch.yaml
"""
from __future__ import annotations
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-chrome-app-launch"

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

ASPECT_PRESETS = {
    "16:9": (1920, 1080),
    "9:16": (540, 960),
    "1:1": (960, 960),
    "4:3": (1280, 960),
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual chrome-app-launch")
    p.add_argument("html_path")
    p.add_argument("--aspect", choices=list(ASPECT_PRESETS.keys()),
                   help="window size を aspect preset で指定")
    p.add_argument("--no-fullscreen", action="store_true",
                   help="fullscreen を抑制（aspect 指定時の既定挙動）")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    return p


def detect_aspect(html_text: str) -> str | None:
    """meta viewport / canvas size / aspect-ratio から推定."""
    m = re.search(r'viewport["\']?\s*content=["\'][^"\']*width=(\d+)', html_text)
    if m:
        w = int(m.group(1))
        if w <= 600:
            return "9:16"
    m = re.search(r'aspect-ratio:\s*(\d+)\s*/\s*(\d+)', html_text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        ratio = a / b
        if abs(ratio - 16/9) < 0.05:
            return "16:9"
        if abs(ratio - 9/16) < 0.05:
            return "9:16"
        if abs(ratio - 1) < 0.05:
            return "1:1"
    return None


def has_cursor_hide(html_text: str) -> bool:
    return bool(re.search(r"cursor\s*:\s*none", html_text))


def run(args: argparse.Namespace) -> int:
    html_path = Path(args.html_path).expanduser().resolve()
    if not html_path.exists():
        logger.error(TOOL_ID, f"html not found: {html_path}")
        return 2
    if not Path(CHROME_BIN).exists():
        logger.error(TOOL_ID, f"Chrome not found at {CHROME_BIN}")
        return 3

    text = html_path.read_text(encoding="utf-8", errors="ignore")
    detected = detect_aspect(text)
    aspect = args.aspect or detected
    if not has_cursor_hide(text):
        print("⚠️  HTML に `cursor: none` の指定が見当たらない。録画時にカーソル写るかも")

    tmpdir = os.environ.get("TMPDIR", "/tmp")
    chrome_args = [
        CHROME_BIN, "--new-window",
        f"--user-data-dir={tmpdir}/emocute-toolkit-chrome",
        f"--app=file://{html_path}",
    ]

    if args.width and args.height:
        chrome_args.append(f"--window-size={args.width},{args.height}")
        mode = f"window-size {args.width}x{args.height}"
    elif aspect and aspect != "16:9":
        w, h = ASPECT_PRESETS[aspect]
        chrome_args.append(f"--window-size={w},{h}")
        mode = f"aspect={aspect} window-size {w}x{h}"
    elif args.no_fullscreen:
        mode = "window default"
    else:
        chrome_args.append("--start-fullscreen")
        mode = "fullscreen"

    print(f"launching Chrome [{mode}]")
    print(f"  html: {html_path}")
    print(f"  cmd:  {' '.join(chrome_args[:1])} ... --app=...")
    logger.info(TOOL_ID, f"launch {html_path.name} mode={mode}",
                meta={"aspect": aspect, "detected": detected})

    # 起動 (block しない)
    subprocess.Popen(chrome_args, start_new_session=True)
    print("✅ Chrome 起動。録画は OBS で。")
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
