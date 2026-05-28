"""site-hreflang-generator — JP/EN ページ対の hreflang 注入.

pages/ 配下から ja / en 両方のページを検出、対になっていれば
`<link rel="alternate" hreflang="...">` の HTML スニペットを生成。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "site-hreflang-generator"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute site hreflang-generator")
    p.add_argument("pages_dir")
    p.add_argument("--base-url", required=True, help="例: https://emocutelab.com")
    p.add_argument("-o", "--out")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.pages_dir).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    pages = list(root.rglob("*.vue"))
    pairs: dict[str, dict[str, str]] = {}
    for p in pages:
        rel = p.relative_to(root)
        parts = rel.with_suffix("").parts
        if not parts:
            continue
        if parts[0] in ("ja", "en"):
            lang = parts[0]
            slug = "/" + "/".join(parts[1:])
        else:
            lang = "ja"
            slug = "/" + "/".join(parts)
        pairs.setdefault(slug, {})[lang] = str(rel)
    snippets = []
    for slug, langs in pairs.items():
        if len(langs) < 2:
            continue
        for lang in ("ja", "en"):
            if lang in langs:
                snippets.append(
                    f'<link rel="alternate" hreflang="{lang}" href="{args.base_url}/{lang}{slug}" />')
        snippets.append(
            f'<link rel="alternate" hreflang="x-default" href="{args.base_url}/ja{slug}" />')
    print(f"pairs:   {sum(1 for v in pairs.values() if len(v)>=2)}")
    print(f"snippets: {len(snippets)}")
    output = "\n".join(snippets)
    if args.out:
        p = Path(args.out).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(output)
        print(f"✅ wrote {p}")
    else:
        print(output[:1000])
    logger.done(TOOL_ID, f"hreflang: {len(snippets)} lines")
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
