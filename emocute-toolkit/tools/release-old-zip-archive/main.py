"""release-old-zip-archive — 旧 ZIP を `_superseded_<date>_<reason>/` に退避.

新版ビルド後に旧ファイル名と中身を比較し、超過分を退避。完全削除はしない。
"""
from __future__ import annotations
import argparse
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "release-old-zip-archive"

VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute release old-zip-archive")
    p.add_argument("dir", help="ZIP が並ぶディレクトリ")
    p.add_argument("--keep", type=int, default=1, help="最新 N 件残す (default 1)")
    p.add_argument("--reason", required=True, help="退避理由 (短く)")
    p.add_argument("--pattern", default="*.zip")
    p.add_argument("--apply", action="store_true")
    return p


def version_key(p: Path) -> tuple:
    m = VERSION_RE.search(p.name)
    if m:
        return tuple(int(x) for x in m.groups())
    return (0, 0, 0)


def group_by_base(files: list[Path]) -> dict[str, list[Path]]:
    """同じ ベース名（version 除く）でグループ化"""
    groups: dict[str, list[Path]] = {}
    for f in files:
        base = VERSION_RE.sub("vX.X.X", f.stem)
        groups.setdefault(base, []).append(f)
    return groups


def run(args: argparse.Namespace) -> int:
    d = Path(args.dir).expanduser().resolve()
    if not d.is_dir():
        logger.error(TOOL_ID, f"not dir: {d}")
        return 2
    files = sorted(d.glob(args.pattern))
    if not files:
        print(f"no files match {args.pattern} in {d}")
        return 0

    groups = group_by_base(files)
    today = dt.date.today().isoformat()
    safe_reason = re.sub(r"[^a-zA-Z0-9_-]", "_", args.reason)
    archive_dir = d / f"_superseded_{today}_{safe_reason}"

    to_move: list[Path] = []
    for base, group in groups.items():
        if len(group) <= args.keep:
            continue
        sorted_group = sorted(group, key=version_key, reverse=True)
        to_move += sorted_group[args.keep:]

    if not to_move:
        print("✅ no old files to archive")
        return 0

    print(f"would archive {len(to_move)} files to {archive_dir.name}/")
    for f in to_move:
        print(f"  {f.name}")
    if not args.apply:
        print("\n[dry-run] use --apply")
        return 0
    archive_dir.mkdir(exist_ok=True)
    for f in to_move:
        dst = archive_dir / f.name
        shutil.move(str(f), str(dst))
        print(f"  ✅ moved {f.name}")
    logger.done(TOOL_ID, f"archived {len(to_move)} files -> {archive_dir.name}")
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
