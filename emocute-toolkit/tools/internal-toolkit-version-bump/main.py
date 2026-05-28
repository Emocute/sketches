"""internal-toolkit-version-bump — toolkit VERSION ファイルの semver bump.

`emocute-toolkit/VERSION` を patch/minor/major で bump し、コミット用文面を生成。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "internal-toolkit-version-bump"


def parse_semver(s: str) -> tuple[int, int, int]:
    parts = s.strip().split(".")
    if len(parts) != 3:
        raise ValueError(f"not semver: {s}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump(v: tuple[int, int, int], kind: str) -> tuple[int, int, int]:
    a, b, c = v
    if kind == "patch":
        return a, b, c + 1
    if kind == "minor":
        return a, b + 1, 0
    if kind == "major":
        return a + 1, 0, 0
    raise ValueError(kind)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute internal toolkit-version-bump")
    p.add_argument("--kind", choices=["patch", "minor", "major"], default="patch")
    p.add_argument("--version-file", default="VERSION")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    vf = Path(args.version_file).expanduser().resolve()
    cur = parse_semver(vf.read_text()) if vf.exists() else (0, 0, 0)
    new = bump(cur, args.kind)
    s_cur = ".".join(str(x) for x in cur)
    s_new = ".".join(str(x) for x in new)
    print(f"current: {s_cur}")
    print(f"new:     {s_new}")
    if not args.apply:
        print("[dry-run]")
        return 0
    vf.write_text(s_new + "\n")
    print(f"✅ wrote {vf}")
    logger.done(TOOL_ID, f"toolkit version: {s_cur} → {s_new}")
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
