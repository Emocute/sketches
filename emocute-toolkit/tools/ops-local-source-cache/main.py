"""ops-local-source-cache — 外部資料のローカルキャッシュ管理.

`~/.cache/emocute/sources/<sha1>/` 配下に web ページ・PDF を保存。
`feedback_local_files` 準拠で調査資料はローカル保持。
"""
from __future__ import annotations
import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "ops-local-source-cache"

CACHE_ROOT = Path("~/.cache/emocute/sources").expanduser()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops local-source-cache")
    p.add_argument("url")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    h = hashlib.sha1(args.url.encode()).hexdigest()
    target_dir = CACHE_ROOT / h[:2] / h
    print(f"url:    {args.url}")
    print(f"cache:  {target_dir}")
    if not args.apply:
        print("[dry-run]")
        return 0
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / "content"
    if out.exists():
        print(f"✅ already cached ({out.stat().st_size} bytes)")
        logger.done(TOOL_ID, "cache hit")
        return 0
    try:
        with urllib.request.urlopen(args.url, timeout=30) as r:
            data = r.read()
    except Exception as e:
        logger.error(TOOL_ID, f"fetch failed: {e}")
        return 3
    out.write_bytes(data)
    (target_dir / "url.txt").write_text(args.url)
    print(f"✅ cached {len(data)} bytes")
    logger.done(TOOL_ID, f"cached {len(data)} bytes")
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
