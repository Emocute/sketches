"""release-album-zip-builder — アルバム ZIP の組み立て.

WAV+MP3+ジャケ+LICENSE+CHANGELOG を集めて
`<title>_v<ver>.zip` に固める。ファイル名にバージョン必須
(`product_title_no_patch_version` & `silent_price_restore_inquiry` 参照)。
"""
from __future__ import annotations
import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "release-album-zip-builder"

REQUIRED = ["LICENSE.md", "CHANGELOG.md"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute release album-zip-builder")
    p.add_argument("src", help="アルバムフォルダ")
    p.add_argument("--version", required=True)
    p.add_argument("--out-dir", default=".")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    src = Path(args.src).expanduser().resolve()
    if not src.is_dir():
        logger.error(TOOL_ID, f"not a dir: {src}")
        return 2
    missing = [r for r in REQUIRED if not (src / r).exists()]
    if missing:
        logger.error(TOOL_ID, f"missing required: {missing}")
        return 2
    files = [p for p in src.rglob("*") if p.is_file() and not p.name.startswith(".")]
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_name = f"{src.name}_v{args.version}.zip"
    out_path = out_dir / out_name
    if out_path.exists():
        logger.error(TOOL_ID, f"already exists: {out_path}. version bump required.")
        return 1
    total_bytes = sum(f.stat().st_size for f in files)
    print(f"src     = {src}")
    print(f"files   = {len(files)}  ({total_bytes/1024/1024:.1f} MB)")
    print(f"output  = {out_path}")
    if not args.apply:
        for f in files[:15]:
            print(f"  • {f.relative_to(src)}")
        if len(files) > 15:
            print(f"  ... ({len(files) - 15} more)")
        print("\n[dry-run]")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.relative_to(src))
    size = out_path.stat().st_size / 1024 / 1024
    print(f"✅ wrote {out_path} ({size:.1f} MB)")
    logger.done(TOOL_ID, f"zip {out_name} {size:.1f}MB")
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
