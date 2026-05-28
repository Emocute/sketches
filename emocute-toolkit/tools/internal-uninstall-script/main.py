"""internal-uninstall-script — toolkit アンインストールスクリプト生成.

`bin/emocute` symlink・launchd plist・git-hook symlink を一括解除する
shell スクリプトを出力。実行は `--apply`、デフォルトは dry-run。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "internal-uninstall-script"

TARGETS = [
    "/usr/local/bin/emocute",
    "~/Library/LaunchAgents/com.emocute.toolkit.notify.plist",
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute internal uninstall-script")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    print("would remove the following links/plists:")
    for t in TARGETS:
        path = Path(t).expanduser()
        flag = "✓ exists" if path.exists() else "✗ missing"
        print(f"  {flag}  {path}")
    if not args.apply:
        print("\n[dry-run] (no files touched)")
        return 0
    removed = 0
    for t in TARGETS:
        path = Path(t).expanduser()
        if path.is_symlink() or path.exists():
            try:
                path.unlink()
                removed += 1
            except OSError as e:
                print(f"  ⚠ failed to remove {path}: {e}")
    print(f"✅ removed {removed} entries")
    logger.done(TOOL_ID, f"uninstall: {removed}")
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
