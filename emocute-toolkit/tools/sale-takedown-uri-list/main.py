"""sale-takedown-uri-list — DMCA takedown 対象 URI のリスト管理.

`takedown_distributor_per_uri` 準拠で URI ごとに distributor (DSP/CDN/mirror)
を識別、申立宛先を出す。
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.parse as up
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "sale-takedown-uri-list"

DISTRIBUTOR_BY_HOST = {
    "open.spotify.com":   ("Spotify",      "https://support.spotify.com/contact"),
    "music.apple.com":    ("Apple Music",  "https://support.apple.com/HT211147"),
    "music.youtube.com":  ("YouTube Music","https://www.youtube.com/dmca"),
    "youtube.com":        ("YouTube",      "https://www.youtube.com/dmca"),
    "soundcloud.com":     ("SoundCloud",   "https://soundcloud.com/pages/copyright"),
    "bandcamp.com":       ("Bandcamp",     "https://get.bandcamp.help/"),
    "deezer.com":         ("Deezer",       "https://www.deezer.com/legal/cgu"),
}


def identify(uri: str) -> tuple[str, str]:
    host = up.urlparse(uri).netloc.lower()
    for key, dest in DISTRIBUTOR_BY_HOST.items():
        if key in host:
            return dest
    return ("(unknown)", "")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute sale takedown-uri-list")
    p.add_argument("uris_file", help="1 行 1 URI のテキストファイル")
    p.add_argument("--json", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    p = Path(args.uris_file).expanduser().resolve()
    if not p.exists():
        logger.error(TOOL_ID, f"not found: {p}")
        return 2
    uris = [l.strip() for l in p.read_text().splitlines() if l.strip()]
    out = []
    for u in uris:
        dist, form = identify(u)
        out.append({"uri": u, "distributor": dist, "claim_form": form})
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        for x in out:
            mark = "⚠" if x["distributor"] == "(unknown)" else " "
            print(f"{mark} {x['distributor']:<14s}  {x['uri']}")
            if x["claim_form"]:
                print(f"    → {x['claim_form']}")
    unknown_count = sum(1 for x in out if x["distributor"] == "(unknown)")
    logger.done(TOOL_ID, f"takedown: {len(out)} uris, {unknown_count} unknown")
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
