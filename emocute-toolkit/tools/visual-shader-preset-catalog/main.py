"""visual-shader-preset-catalog — GLSL/HLSL シェーダプリセット一覧.

Visual で使用する vertex/fragment shader プリセットを名前+用途で索引化。
シーン構築時の「あの effect どこ?」を解決。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-shader-preset-catalog"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual shader-preset-catalog")
    p.add_argument("shader_dir", help="シェーダディレクトリ")
    p.add_argument("--ext", nargs="+", default=[".glsl", ".frag", ".vert", ".hlsl"])
    p.add_argument("--json", action="store_true")
    return p


def parse_header(path: Path) -> dict:
    """先頭 30 行から // @key value 形式のメタを抽出"""
    meta: dict = {}
    try:
        for line in path.read_text(errors="ignore").splitlines()[:30]:
            line = line.strip()
            if line.startswith("// @"):
                rest = line[4:].strip()
                if " " in rest:
                    k, _, v = rest.partition(" ")
                    meta[k] = v.strip()
    except Exception:
        pass
    return meta


def run(args: argparse.Namespace) -> int:
    root = Path(args.shader_dir).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    entries = []
    for ext in args.ext:
        for f in root.rglob(f"*{ext}"):
            meta = parse_header(f)
            entries.append({
                "path": str(f.relative_to(root)),
                "name": meta.get("name", f.stem),
                "tag": meta.get("tag", ""),
                "use": meta.get("use", ""),
            })
    if args.json:
        print(json.dumps(entries, indent=2, ensure_ascii=False))
    else:
        print(f"shaders: {len(entries)}")
        for e in entries:
            print(f"  {e['name']:<24s}  [{e['tag']}]  {e['use']}")
            print(f"      {e['path']}")
    logger.done(TOOL_ID, f"shaders: {len(entries)}")
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
