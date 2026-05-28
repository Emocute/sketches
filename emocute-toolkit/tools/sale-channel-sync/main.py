"""sale-channel-sync — 商品メタデータを BOOTH/Gumroad/itch.io 間で揃える.

各チャネル ID と price を YAML に集約し、差分のあるチャネルを警告。
タイトル本体は同じ表記、ファイル ZIP は別管理。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-channel-sync"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale channel-sync")
    p.add_argument("manifest", help="products YAML")
    p.add_argument("--json", action="store_true")
    return p


def load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        logger.error(TOOL_ID, "pip install pyyaml")
        return {}
    return yaml.safe_load(path.read_text()) or {}


def run(args: argparse.Namespace) -> int:
    manifest = Path(args.manifest).expanduser().resolve()
    if not manifest.exists():
        logger.error(TOOL_ID, f"not found: {manifest}")
        return 2
    data = load_yaml(manifest)
    products = data.get("products", [])
    issues = []
    for p in products:
        name = p.get("name", "(unnamed)")
        channels = p.get("channels", {})
        # collect prices per currency
        jp_prices = []
        usd_prices = []
        for ch, info in channels.items():
            if not isinstance(info, dict):
                continue
            if "price_jpy" in info:
                jp_prices.append((ch, info["price_jpy"]))
            if "price_usd" in info:
                usd_prices.append((ch, info["price_usd"]))
        # JP price mismatch
        if len({pr for _, pr in jp_prices}) > 1:
            issues.append({"product": name, "type": "price_jpy_mismatch",
                           "detail": dict(jp_prices)})
        if len({pr for _, pr in usd_prices}) > 1:
            issues.append({"product": name, "type": "price_usd_mismatch",
                           "detail": dict(usd_prices)})
        # missing channel ID
        for ch, info in channels.items():
            if isinstance(info, dict) and not info.get("id") and not info.get("url"):
                issues.append({"product": name, "type": "missing_id",
                               "detail": ch})

    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    else:
        print(f"checked {len(products)} products, {len(issues)} issues")
        for i in issues[:30]:
            print(f"  [{i['type']}] {i['product']}: {i['detail']}")
    if issues:
        logger.warn(TOOL_ID, f"{len(issues)} sync issues")
        return 1
    logger.done(TOOL_ID, f"{len(products)} products in sync")
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
