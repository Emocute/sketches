"""visual-mvtool-autopilot — Visual/mvtool.py の標準パイプライン自動化.

新規 MV 制作の典型フロー（録画 → trim → scale → letterbox → platform versions）
を 1 コマンドで通す wrapper。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-mvtool-autopilot"

TOOLKIT_ROOT = Path(__file__).resolve().parents[2]


def call_tool(tool_id: str, args: list[str]) -> int:
    """toolkit 内の別ツールを呼ぶ（CLI 経由）"""
    script = TOOLKIT_ROOT / "tools" / tool_id / "main.py"
    if not script.exists():
        return 2
    return subprocess.run([sys.executable, str(script)] + args).returncode


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual mvtool-autopilot")
    p.add_argument("input")
    p.add_argument("--stages", default="trim,scale,platforms",
                   help="csv from trim,scale,platforms,thumb,verify")
    p.add_argument("--out-dir", help="default = input parent")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else inp.parent
    stages = [s.strip() for s in args.stages.split(",")]
    cur = inp
    print(f"input: {inp.name}  stages: {stages}")

    if "trim" in stages:
        rc = call_tool("visual-silence-trim",
                       [str(cur)] + (["--apply"] if args.apply else []))
        if rc != 0:
            return rc
        if args.apply:
            cur = cur.with_name(f"{cur.stem}_trimmed{cur.suffix}")
    if "scale" in stages:
        rc = call_tool("visual-scale-pad-even",
                       [str(cur)] + (["--apply"] if args.apply else []))
        if rc != 0:
            return rc
    if "platforms" in stages:
        rc = call_tool("visual-platform-versions",
                       [str(cur), "--out-dir", str(out_dir)]
                       + (["--apply"] if args.apply else []))
        if rc != 0:
            return rc
    if "thumb" in stages:
        rc = call_tool("visual-thumbnail-multi-aspect",
                       [str(cur), "--out-dir", str(out_dir)]
                       + (["--apply"] if args.apply else []))
        if rc != 0:
            return rc
    if "verify" in stages:
        rc = call_tool("visual-ffprobe-verify", [str(out_dir)])
        if rc != 0:
            return rc

    if not args.apply:
        print("\n[dry-run] use --apply to execute stages")
    else:
        print("✅ autopilot complete")
    logger.done(TOOL_ID, f"autopilot {len(stages)} stages")
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
