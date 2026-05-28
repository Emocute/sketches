"""visual-hls-streaming-preview — HLS のローカルプレビュー用 http サーバ.

`visual-hls-segment` で生成した m3u8 + ts をローカルで配信するための
プレビューサーバ仕様 (CORS 対応)。Python http.server を薄くラップ。
"""
from __future__ import annotations
import argparse
import functools
import http.server
import socketserver
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-hls-streaming-preview"


class CORSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual hls-streaming-preview")
    p.add_argument("dir", help="m3u8/ts のあるディレクトリ")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.dir).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    m3u8s = list(root.glob("*.m3u8"))
    print(f"dir:    {root}")
    print(f"m3u8:   {len(m3u8s)}")
    for m in m3u8s[:3]:
        print(f"  http://localhost:{args.port}/{m.name}")
    if not args.apply:
        print("\n[dry-run] use --apply to start CORS http server")
        return 0
    handler = functools.partial(CORSHandler, directory=str(root))
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        print(f"serving on http://localhost:{args.port}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    logger.done(TOOL_ID, f"hls preview on :{args.port}")
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
