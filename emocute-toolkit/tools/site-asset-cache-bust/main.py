"""site-asset-cache-bust — public/ 配下の差し替えで ?v= バストを自動付与.

`vercel_static_asset_cache_bust` 準拠。public/ の対象ファイルが変わった時、
ソース内の参照 (`src="/foo.png"`) を `?v=YYYYMMDD` 付きに置換。
"""
from __future__ import annotations
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "site-asset-cache-bust"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site asset-cache-bust")
    p.add_argument("site_root")
    p.add_argument("asset_basename", help="例: hero.png (public/ 配下)")
    p.add_argument("--version")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.site_root).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    version = args.version or dt.date.today().strftime("%Y%m%d")
    name = args.asset_basename
    pat = re.compile(rf'/{re.escape(name)}(\?v=\d+)?')
    affected = []
    for f in root.rglob("*.vue"):
        if "node_modules" in str(f):
            continue
        text = f.read_text(errors="ignore")
        if name not in text:
            continue
        new_text = pat.sub(f"/{name}?v={version}", text)
        if new_text != text:
            affected.append((f, new_text))
    print(f"asset:   /{name}")
    print(f"version: ?v={version}")
    print(f"files:   {len(affected)}")
    for f, _ in affected:
        print(f"  • {f.relative_to(root)}")
    if not args.apply:
        print("\n[dry-run]")
        return 0
    for f, new in affected:
        f.write_text(new)
    print(f"\n✅ updated {len(affected)} files")
    logger.done(TOOL_ID, f"bust {name} v={version}, {len(affected)} files")
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
