"""studio-chord-dict-sync — 楽曲別コードシートの同期 / 統合辞書.

`Studio/sessions/<song>/chords.yaml` を読み込んで、トップレベルの
`Studio/chord_dict.yaml` に統合 (song_id → progression リスト)。
HarmonyScope の chord catalog と相互参照可能なフォーマット。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-chord-dict-sync"


def parse_simple_yaml(path: Path) -> dict:
    """超簡易 YAML パーサ (key: value, key: [..] のみ対応)"""
    result: dict = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        result[k.strip()] = v
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio chord-dict-sync")
    p.add_argument("sessions_dir", help="Studio/sessions ルート")
    p.add_argument("-o", "--out", default="Studio/chord_dict.json")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    root = Path(args.sessions_dir).expanduser().resolve()
    if not root.exists():
        logger.error(TOOL_ID, f"not found: {root}")
        return 2
    out = Path(args.out).expanduser().resolve()
    dict_data: dict[str, dict] = {}
    yamls = list(root.rglob("chords.yaml"))
    for y in yamls:
        song = y.parent.name
        try:
            data = parse_simple_yaml(y)
        except Exception as e:
            logger.warn(TOOL_ID, f"skip {y}: {e}")
            continue
        dict_data[song] = data
    print(f"songs scanned: {len(yamls)}")
    print(f"merged: {len(dict_data)}")
    if not args.apply:
        for song in list(dict_data)[:5]:
            print(f"  {song}: {list(dict_data[song].keys())}")
        print("\n[dry-run]")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict_data, indent=2, ensure_ascii=False))
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"chord dict: {len(dict_data)} songs")
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
