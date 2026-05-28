"""game-kagebu-zip-builder — Kagebu/Umbrae 配布 ZIP の組立.

`personas_master/` から最新人格データ + LICENSE + README + 試用版 を集めて
`Kagebu_v<X.Y.Z>.zip` を作る。`project_kagebu_v1_9_3_launch_decisions_2026-05-22`
準拠で価格・試用は別管理。
"""
from __future__ import annotations
import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-kagebu-zip-builder"

REQUIRED = ["LICENSE.md", "README.md"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game kagebu-zip-builder")
    p.add_argument("kagebu_root", help="Kagebu/")
    p.add_argument("--version", required=True)
    p.add_argument("--out-dir", default="_export")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.kagebu_root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    missing = [r for r in REQUIRED if not (root / r).exists()]
    if missing:
        logger.error(TOOL_ID, f"missing required: {missing}")
        return 2
    masters = root / "personas_master"
    if not masters.exists():
        logger.error(TOOL_ID, f"no personas_master/ in {root}")
        return 2
    files = []
    for f in masters.rglob("*.md"):
        files.append(f)
    for r in REQUIRED:
        files.append(root / r)
    out_dir = root / args.out_dir
    out_path = out_dir / f"Kagebu_v{args.version}.zip"
    if out_path.exists():
        logger.error(TOOL_ID, f"already exists: {out_path}. version bump required.")
        return 1
    total = sum(f.stat().st_size for f in files)
    print(f"version:  v{args.version}")
    print(f"files:    {len(files)} ({total/1024/1024:.1f} MB)")
    print(f"out:      {out_path}")
    if not args.apply:
        for f in files[:10]:
            print(f"  • {f.relative_to(root)}")
        if len(files) > 10:
            print(f"  ... ({len(files) - 10} more)")
        print("\n[dry-run]")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.relative_to(root))
    size = out_path.stat().st_size / 1024 / 1024
    print(f"✅ wrote {out_path} ({size:.1f} MB)")
    logger.done(TOOL_ID, f"kagebu zip v{args.version} ({size:.1f}MB)")
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
