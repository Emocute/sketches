"""visual-color-space-verify — 動画ファイルのカラースペース検証.

ffprobe で BT.601/709/2020/sRGB の判定、HDR (HLG/PQ) 判定。
販売物として均一化する時の事前チェック。
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-color-space-verify"


def probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def classify(stream: dict) -> str:
    cs = stream.get("color_space") or ""
    tx = stream.get("color_transfer") or ""
    if tx in ("smpte2084", "arib-std-b67"):
        return f"HDR ({tx})"
    if cs in ("bt2020nc", "bt2020c"):
        return "BT.2020"
    if cs in ("bt709",):
        return "BT.709"
    if cs in ("smpte170m", "bt470bg"):
        return "BT.601"
    return cs or "(unknown)"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual color-space-verify")
    p.add_argument("inputs", nargs="+")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    out = []
    for f in args.inputs:
        path = Path(f).expanduser().resolve()
        if not path.exists():
            logger.warn(TOOL_ID, f"skip missing: {f}")
            continue
        try:
            data = probe(path)
        except subprocess.CalledProcessError as e:
            logger.error(TOOL_ID, f"ffprobe failed on {f}: {e}")
            continue
        v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        if not v:
            continue
        info = {
            "file": path.name,
            "classification": classify(v),
            "color_space": v.get("color_space"),
            "color_transfer": v.get("color_transfer"),
            "color_primaries": v.get("color_primaries"),
            "pix_fmt": v.get("pix_fmt"),
        }
        out.append(info)
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"{'file':<40} {'class':<15} {'transfer':<14} pix_fmt")
        print("-" * 90)
        for i in out:
            print(f"{i['file'][:40]:<40} {i['classification']:<15} {str(i['color_transfer'] or '-'):<14} {i['pix_fmt']}")
    logger.done(TOOL_ID, f"checked: {len(out)}")
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
