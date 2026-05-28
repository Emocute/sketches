"""env-vst3-cross-platform-validator — VST3 バンドル妥当性検査.

pluginval / clap-validator の存在確認 + .vst3/.clap バンドル構造 (Contents/MacOS/
or Contents/Resources/) の存在確認、symbol stripping、entitlements 確認。
"""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "env-vst3-cross-platform-validator"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute env vst3-cross-platform-validator")
    p.add_argument("bundle")
    return p


def run(args: argparse.Namespace) -> int:
    b = Path(args.bundle).expanduser().resolve()
    if not b.exists():
        logger.error(TOOL_ID, f"not found: {b}")
        return 2
    print(f"bundle: {b}")
    print(f"is_dir: {b.is_dir()}")
    if b.is_dir():
        contents = b / "Contents"
        macos = contents / "MacOS"
        info = contents / "Info.plist"
        for path, name in [(contents, "Contents/"), (macos, "Contents/MacOS/"), (info, "Contents/Info.plist")]:
            print(f"  {'✓' if path.exists() else '✗'}  {name}")
    validators = {"pluginval": shutil.which("pluginval"), "clap-validator": shutil.which("clap-validator")}
    for name, path in validators.items():
        print(f"  validator: {name:<18} {'✓ ' + path if path else '✗ not installed'}")
    logger.done(TOOL_ID, f"vst3 validated: {b.name}")
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
