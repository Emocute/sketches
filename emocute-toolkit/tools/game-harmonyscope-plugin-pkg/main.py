"""game-harmonyscope-plugin-pkg — VST3/CLAP プラグインパッケージング.

cargo build --release 完了後、`target/release/` 配下から .vst3/.clap バンドルを
`_export/HarmonyScope_v<X.Y.Z>_<os>.zip` に固める。
"""
from __future__ import annotations
import argparse
import platform
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-harmonyscope-plugin-pkg"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game harmonyscope-plugin-pkg")
    p.add_argument("workspace_root")
    p.add_argument("--version", required=True)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.workspace_root).expanduser().resolve()
    rel = root / "target" / "release"
    if not rel.exists():
        logger.error(TOOL_ID, f"no target/release/. build first.")
        return 2
    bundles = list(rel.glob("*.vst3")) + list(rel.glob("*.clap"))
    if not bundles:
        logger.warn(TOOL_ID, "no .vst3 / .clap bundles found")
        return 1
    os_tag = {"Darwin": "macos", "Linux": "linux", "Windows": "win"}.get(platform.system(), "unknown")
    out = root / "_export" / f"HarmonyScope_v{args.version}_{os_tag}.zip"
    print(f"bundles: {len(bundles)}")
    for b in bundles:
        print(f"  • {b.name}")
    print(f"out:     {out}")
    if not args.apply:
        print("[dry-run]")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for b in bundles:
            if b.is_dir():
                for f in b.rglob("*"):
                    if f.is_file():
                        z.write(f, f.relative_to(rel))
            else:
                z.write(b, b.name)
    size = out.stat().st_size / 1024 / 1024
    print(f"✅ wrote {out} ({size:.1f} MB)")
    logger.done(TOOL_ID, f"hs plugin pkg v{args.version} ({size:.1f}MB)")
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
