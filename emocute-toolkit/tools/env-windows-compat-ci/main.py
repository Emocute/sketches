"""env-windows-compat-ci — Windows 互換 CI ワークフロー雛形生成.

GitHub Actions の `windows-latest` runner で HarmonyScope の cargo
test/build を回す YAML を出力。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "env-windows-compat-ci"

YAML = """name: windows-compat
on:
  push:
    branches: [main]
  pull_request:
jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions-rust-lang/setup-rust-toolchain@v1
        with:
          toolchain: stable
      - run: cargo check --all-targets
      - run: cargo test --release
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute env windows-compat-ci")
    p.add_argument("-o", "--out", default="-")
    return p


def run(args: argparse.Namespace) -> int:
    if args.out == "-":
        print(YAML)
    else:
        Path(args.out).expanduser().resolve().write_text(YAML)
        print(f"✅ wrote {args.out}")
    logger.done(TOOL_ID, "win-ci yaml emitted")
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
