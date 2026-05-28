"""game-harmonyscope-cargo-runner — HarmonyScope cargo ビルド/テストの実行.

`HarmonyScope/` の Rust workspace を `cargo check / test / build --release` で回す薄ラッパ。
"""
from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-harmonyscope-cargo-runner"

ALLOWED = ["check", "test", "build", "fmt", "clippy"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game harmonyscope-cargo-runner")
    p.add_argument("workspace_root", help="HarmonyScope/")
    p.add_argument("--cmd", choices=ALLOWED, default="check")
    p.add_argument("--release", action="store_true")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.workspace_root).expanduser().resolve()
    if not (root / "Cargo.toml").exists():
        logger.error(TOOL_ID, f"no Cargo.toml in {root}")
        return 2
    if shutil.which("cargo") is None:
        logger.error(TOOL_ID, "cargo not installed")
        return 3
    cmd = ["cargo", args.cmd]
    if args.release and args.cmd in {"build", "test"}:
        cmd.append("--release")
    print(f"workspace: {root}")
    print(f"command:   {' '.join(cmd)}")
    if not args.apply:
        print("[dry-run]")
        return 0
    r = subprocess.run(cmd, cwd=root)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"cargo {args.cmd} failed: {r.returncode}")
        return 1
    logger.done(TOOL_ID, f"cargo {args.cmd} ok")
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
