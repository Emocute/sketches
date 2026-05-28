"""release-bump-version — 販売物 ZIP の version bump + CHANGELOG prepend + 旧 ZIP 退避.

spec: registry/release/release-bump-version.yaml
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import io
import re
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "release-bump-version"

# 'foo_v1.2.3.zip' 'foo-v8.1.zip' 'foo-1.2.zip' を許容
VERSION_RE = re.compile(r"(.*?)([_-])(v?)(\d+)\.(\d+)(?:\.(\d+))?(.+\.zip)$",
                        re.IGNORECASE)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute release bump-version")
    p.add_argument("zip_dir", help="販売物 ZIP が並ぶフォルダ")
    p.add_argument("--target", choices=["patch", "minor", "major"], default="patch")
    p.add_argument("--reason", default="content_changed")
    p.add_argument("--apply", action="store_true",
                   help="実書込（既定 dry-run）")
    return p


def parse_version(name: str) -> tuple[str, str, str, tuple[int, int, int], str] | None:
    m = VERSION_RE.match(name)
    if not m:
        return None
    prefix, sep, vp, maj, minr, pat, tail = m.groups()
    return (prefix, sep, vp,
            (int(maj), int(minr), int(pat) if pat else 0),
            tail)


def bump(v: tuple[int, int, int], kind: str) -> tuple[int, int, int]:
    a, b, c = v
    if kind == "major":
        return (a + 1, 0, 0)
    if kind == "minor":
        return (a, b + 1, 0)
    return (a, b, c + 1)


def fmt_version(v: tuple[int, int, int], has_patch: bool) -> str:
    if has_patch:
        return f"{v[0]}.{v[1]}.{v[2]}"
    return f"{v[0]}.{v[1]}"


def zip_content_hash(path: Path) -> str:
    """ZIP 内全エントリの (name, size, crc) を順序固定でハッシュ."""
    h = hashlib.sha256()
    with zipfile.ZipFile(path) as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            h.update(info.filename.encode("utf-8"))
            h.update(str(info.file_size).encode())
            h.update(f"{info.CRC:08x}".encode())
    return h.hexdigest()


def find_latest_pair(zip_dir: Path) -> dict[str, list[Path]]:
    """prefix ごとに version 昇順のリスト."""
    groups: dict[str, list[tuple[tuple[int, int, int], Path]]] = {}
    for z in zip_dir.glob("*.zip"):
        info = parse_version(z.name)
        if info is None:
            continue
        prefix = info[0]
        groups.setdefault(prefix, []).append((info[3], z))
    out: dict[str, list[Path]] = {}
    for k, lst in groups.items():
        lst.sort()
        out[k] = [p for _, p in lst]
    return out


def prepend_changelog(pj_root: Path, new_version: str, reason: str) -> Path:
    cl = pj_root / "CHANGELOG.md"
    today = dt.date.today().isoformat()
    new_block = (
        f"## {new_version} — {today}\n"
        f"- {reason}\n\n"
    )
    if cl.exists():
        old = cl.read_text(encoding="utf-8")
        if "# Changelog" in old:
            new = old.replace("# Changelog\n", "# Changelog\n\n" + new_block, 1)
        else:
            new = "# Changelog\n\n" + new_block + old
        cl.write_text(new, encoding="utf-8")
    else:
        cl.write_text("# Changelog\n\n" + new_block, encoding="utf-8")
    return cl


def embed_version_file(src_zip: Path, dst_zip: Path, version: str) -> None:
    with zipfile.ZipFile(src_zip) as src, \
         zipfile.ZipFile(dst_zip, "w", zipfile.ZIP_DEFLATED) as dst:
        wrote_version = False
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename.endswith("VERSION") or info.filename == "VERSION":
                data = version.encode("utf-8")
                wrote_version = True
            dst.writestr(info, data)
        if not wrote_version:
            dst.writestr("VERSION", version.encode("utf-8"))


def run(args: argparse.Namespace) -> int:
    zip_dir = Path(args.zip_dir).expanduser().resolve()
    if not zip_dir.is_dir():
        logger.error(TOOL_ID, f"not a directory: {zip_dir}")
        return 2

    groups = find_latest_pair(zip_dir)
    if not groups:
        logger.error(TOOL_ID, f"no versioned ZIPs in {zip_dir} (pattern: foo_vX.Y[.Z].zip)")
        return 1

    print(f"found {len(groups)} version groups in {zip_dir}")
    proposals = []
    for prefix, paths in groups.items():
        latest = paths[-1]
        info = parse_version(latest.name)
        assert info
        _, sep, vp, ver, tail = info
        has_patch = bool(re.match(r".*?\d+\.\d+\.\d+", latest.name))
        next_ver = bump(ver, args.target)
        new_name = f"{prefix}{sep}{vp}{fmt_version(next_ver, has_patch)}{tail}"
        new_path = zip_dir / new_name
        # hash compare (latest と "次に作りたい新版" の比較は新版が無いので、
        # 単純に「version bump 用」コマンドとして提案を出す)
        cur_hash = zip_content_hash(latest)
        proposals.append({
            "prefix": prefix,
            "latest_name": latest.name,
            "latest_path": latest,
            "latest_version": fmt_version(ver, has_patch),
            "next_version": fmt_version(next_ver, has_patch),
            "next_name": new_name,
            "next_path": new_path,
            "cur_hash": cur_hash[:12],
        })

    print()
    for p in proposals:
        print(f"  {p['latest_name']}  (hash {p['cur_hash']})")
        print(f"    → {p['next_name']}  ({args.target} bump)")

    if not args.apply:
        print(f"\n[dry-run] use --apply to bump (target={args.target}, reason={args.reason})")
        return 0

    today = dt.date.today().isoformat()
    superseded_dir = zip_dir / f"_superseded_{today}_{args.reason}"
    superseded_dir.mkdir(exist_ok=True)

    for p in proposals:
        # embed VERSION + copy as new
        new_zip = p["next_path"]
        if new_zip.exists():
            logger.warn(TOOL_ID, f"target exists, skipping: {new_zip.name}")
            continue
        embed_version_file(p["latest_path"], new_zip, p["next_version"])
        # 旧 ZIP を退避
        shutil.move(str(p["latest_path"]), str(superseded_dir / p["latest_path"].name))
        # CHANGELOG prepend
        prepend_changelog(zip_dir.parent, p["next_version"],
                          f"{p['prefix']}: {args.reason}")
        print(f"  ✅ {p['latest_name']} -> {new_zip.name}")
        logger.done(TOOL_ID, f"bumped {p['latest_name']} -> {new_zip.name}",
                    meta={"reason": args.reason})

    print(f"\nold zips moved to: {superseded_dir.name}/")
    print(f"CHANGELOG updated: {zip_dir.parent / 'CHANGELOG.md'}")
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
