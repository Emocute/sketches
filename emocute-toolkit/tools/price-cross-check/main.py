"""price-cross-check — 価格 cross-check（memory / Site / BOOTH / Gumroad）.

spec: registry/price/price-cross-check.yaml

実装方針:
  - memory: ~/.claude/projects/.../memory/*.md から `¥xxx` / `$xxx` を抽出
  - site: Site/data/products.ts または Sale/business/*.yaml から抽出
  - booth: 認証必要なので credentials がある場合のみ
  - gumroad: access_token がある場合のみ
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import config, logger  # noqa: E402

TOOL_ID = "price-cross-check"

MEMORY_ROOT = Path.home() / ".claude" / "projects" / "-Users-emocute-Downloads" / "memory"

# 価格パターン
PRICE_JPY = re.compile(r"¥\s*([\d,]+)")
PRICE_USD = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")

# 商品名 → memory ファイル中で対応関係を推定するための候補
# 既知商品リスト
KNOWN_PRODUCTS = [
    "Umbrae", "Kagebu", "Studio", "Visual",
    "HarmonyScope", "Numbloom", "Idiograph",
    "アルバム", "Pack", "Toolkit",
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute price cross-check")
    p.add_argument("--json", action="store_true")
    p.add_argument("--fix-from", choices=["memory", "site", "booth", "gumroad"],
                   help="この source を正として diff 提案")
    return p


def scan_memory() -> dict[str, list[tuple[int, int, str]]]:
    """returns {product: [(price_jpy, price_usd, source_file), ...]}"""
    out: dict[str, list[tuple[int, int, str]]] = {}
    if not MEMORY_ROOT.exists():
        return out
    for path in MEMORY_ROOT.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # 行ベースで「商品名 ... 価格」 のパターンを探す
        for line in text.splitlines():
            jpy_match = PRICE_JPY.search(line)
            usd_match = PRICE_USD.search(line)
            if not (jpy_match or usd_match):
                continue
            for prod in KNOWN_PRODUCTS:
                if prod in line or prod in path.stem:
                    jpy = int(jpy_match.group(1).replace(",", "")) if jpy_match else 0
                    usd = int(float(usd_match.group(1))) if usd_match else 0
                    out.setdefault(prod, []).append((jpy, usd, path.name))
                    break
    return out


def scan_site() -> dict[str, tuple[int, int]]:
    """returns {product_name: (jpy, usd)}"""
    out: dict[str, tuple[int, int]] = {}
    try:
        site_root = config.pj_path("Site")
    except KeyError:
        return out
    candidates = [
        site_root / "data" / "products.ts",
        site_root / "data" / "albums.ts",
        site_root / "data" / "products.json",
    ]
    sale_root = config.pj_path("Sale") if "Sale" in config.pj_map() else None
    if sale_root and sale_root.exists():
        candidates += list(sale_root.glob("business/*.yaml"))
    for c in candidates:
        if not c.exists() or not c.is_file():
            continue
        try:
            text = c.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # 雑パース: name/title と price_jpy/price_usd ペア
        # TS: { id: 'x', title: '...', priceJpy: 5800, priceUsd: 29 }
        for m in re.finditer(r"(?:title|name|id)\s*[:=]\s*['\"]([^'\"]+)['\"][^}]*?price[_]?[Jj]py\s*[:=]\s*(\d+)[^}]*?price[_]?[Uu]sd\s*[:=]\s*(\d+(?:\.\d+)?)", text, re.DOTALL):
            name, jpy, usd = m.group(1), int(m.group(2)), int(float(m.group(3)))
            out[name] = (jpy, usd)
        # YAML: name: ... \n price_jpy: ...
        # 単純に「直近の name 値 → その後の price」
        cur_name = None
        for line in text.splitlines():
            nm = re.match(r"\s*(?:name|title|id)\s*:\s*['\"]?([^'\"]+?)['\"]?\s*$", line)
            if nm:
                cur_name = nm.group(1).strip()
                continue
            pm = re.match(r"\s*price_jpy\s*:\s*(\d+)", line)
            if pm and cur_name:
                jpy = int(pm.group(1))
                # 次の行で usd 探す: 単純化のため別途
                out.setdefault(cur_name, (jpy, 0))
    return out


def normalize_jpy(jpy: int) -> int:
    return jpy


def run(args: argparse.Namespace) -> int:
    mem = scan_memory()
    site = scan_site()

    # 全 product を結合
    all_products = set(mem.keys()) | set(site.keys())
    if not all_products:
        logger.warn(TOOL_ID, "no products with prices found in memory/site")
        if args.json:
            print(json.dumps({"sources": {}, "diff": []}, indent=2))
        else:
            print("⚠️  no products with prices found")
        return 1

    rows = []
    diffs = []
    for prod in sorted(all_products):
        mem_records = mem.get(prod, [])
        site_jpy, site_usd = site.get(prod, (None, None))
        # memory 内 unique 値
        mem_jpy_set = sorted({r[0] for r in mem_records if r[0]})
        mem_usd_set = sorted({r[1] for r in mem_records if r[1]})
        row = {
            "product": prod,
            "memory_jpy": mem_jpy_set,
            "memory_usd": mem_usd_set,
            "site_jpy": site_jpy,
            "site_usd": site_usd,
        }
        rows.append(row)
        # diff 判定: memory に複数値あり or memory と site で不一致
        if len(mem_jpy_set) > 1 or len(mem_usd_set) > 1:
            diffs.append({"product": prod, "issue": "memory inconsistent",
                          "values": {"jpy": mem_jpy_set, "usd": mem_usd_set}})
        if site_jpy and mem_jpy_set and site_jpy not in mem_jpy_set:
            diffs.append({"product": prod, "issue": "site vs memory mismatch",
                          "site_jpy": site_jpy, "memory_jpy": mem_jpy_set})

    if args.json:
        print(json.dumps({"rows": rows, "diffs": diffs}, ensure_ascii=False, indent=2))
    else:
        print(f"{'product':<20} {'memory jpy':<20} {'memory usd':<15} {'site jpy':<10} {'site usd':<10}")
        print("-" * 80)
        for r in rows:
            print(f"{r['product']:<20} "
                  f"{str(r['memory_jpy'])[:18]:<20} "
                  f"{str(r['memory_usd'])[:13]:<15} "
                  f"{str(r['site_jpy'] or '-'):<10} "
                  f"{str(r['site_usd'] or '-'):<10}")
        if diffs:
            print(f"\n❌ {len(diffs)} inconsistencies:")
            for d in diffs:
                print(f"  - {d['product']}: {d['issue']}")
        else:
            print("\n✅ all sources consistent")

    if diffs:
        logger.error(TOOL_ID, f"price drift: {len(diffs)} issues")
        return 2
    logger.done(TOOL_ID, f"checked {len(rows)} products, all consistent")
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
