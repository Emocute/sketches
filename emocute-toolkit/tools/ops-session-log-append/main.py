"""ops-session-log-append — SESSION_LOG.md 自動追記.

spec: registry/ops/ops-session-log-append.yaml
"""
from __future__ import annotations
import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import config, logger  # noqa: E402

TOOL_ID = "ops-session-log-append"

SECTION_RE = re.compile(r"^## ([0-9a-f]{8})\s+(.+)$", re.MULTILINE)
MAX_BYTES = 200 * 1024  # 200KB で分離検討


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute ops session-log-append")
    p.add_argument("--pj", required=True, help="対象 PJ 名（pj_map.yaml キー）")
    p.add_argument("--uuid", required=True, help="セッション UUID（先頭 8 字を使用）")
    p.add_argument("--phase", choices=["start", "end"], required=True)
    p.add_argument("--summary", default="")
    p.add_argument("--apply", action="store_true",
                   help="--apply 無しでも実書込（既定 true）。dry にするには --dry")
    p.add_argument("--dry", action="store_true")
    return p


def get_log_path(pj: str) -> Path:
    try:
        root = config.pj_path(pj)
    except KeyError:
        # fallback: cwd basename
        if pj == os.path.basename(os.getcwd()):
            root = Path.cwd()
        else:
            raise
    return root / "SESSION_LOG.md"


def get_recent_commits(pj_path: Path, since_iso: str | None) -> list[str]:
    """since_iso 以降の commit 一覧（短ハッシュ + subject）."""
    if not (pj_path / ".git").exists() and not (pj_path.parent / ".git").exists():
        # モノレポルートで動いてる可能性
        pass
    try:
        cmd = ["git", "-C", str(pj_path), "log", "--oneline", "-20"]
        if since_iso:
            cmd.insert(-1, f"--since={since_iso}")
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            return proc.stdout.strip().splitlines()
    except OSError:
        pass
    return []


def rotate_if_large(log_path: Path) -> None:
    if not log_path.exists():
        return
    size = log_path.stat().st_size
    if size <= MAX_BYTES:
        return
    yyyymm = dt.datetime.now().strftime("%Y%m")
    archive_dir = log_path.parent / "_archive"
    archive_dir.mkdir(exist_ok=True)
    target = archive_dir / f"SESSION_LOG_{yyyymm}.md"
    # 先頭 80% をアーカイブに移送、末尾は残す
    text = log_path.read_text(encoding="utf-8")
    cut = int(len(text) * 0.8)
    # 直近 section の境界で切る
    sec_starts = [m.start() for m in SECTION_RE.finditer(text)]
    cut_pos = min((s for s in sec_starts if s >= cut), default=cut)
    head, tail = text[:cut_pos], text[cut_pos:]
    archive_existing = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(archive_existing + head, encoding="utf-8")
    log_path.write_text(f"<!-- rotated to _archive/SESSION_LOG_{yyyymm}.md -->\n\n" + tail,
                        encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    log_path = get_log_path(args.pj)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text("# SESSION_LOG\n\n", encoding="utf-8")
        logger.info(TOOL_ID, f"created {log_path}")

    uuid_short = args.uuid[:8]
    now = dt.datetime.now()
    iso_now = now.astimezone().isoformat(timespec="seconds")
    date = now.date().isoformat()

    text = log_path.read_text(encoding="utf-8")

    if args.phase == "start":
        new_section = (
            f"\n## {uuid_short} {date}\n"
            f"- start: {iso_now}\n"
            f"- cwd: {os.getcwd()}\n"
            f"- pj: {args.pj}\n"
        )
        new_text = text.rstrip() + "\n" + new_section
        action_desc = f"start {uuid_short}"
    else:  # end
        # 既存 section を検索
        m = None
        for mm in SECTION_RE.finditer(text):
            if mm.group(1) == uuid_short:
                m = mm
        # section の終端 = 次 section start or eof
        if m:
            next_starts = [mm.start() for mm in SECTION_RE.finditer(text) if mm.start() > m.start()]
            insert_pos = next_starts[0] if next_starts else len(text)
            # start: timestamp を取得して since とする
            section_text = text[m.start(): insert_pos]
            sm = re.search(r"- start:\s*(\S+)", section_text)
            since = sm.group(1) if sm else None
            commits = get_recent_commits(log_path.parent, since)
            addendum_lines = [
                f"- end: {iso_now}",
                f"- summary: {args.summary}" if args.summary else "",
            ]
            if commits:
                addendum_lines.append("- commits:")
                addendum_lines.extend(f"  - {c}" for c in commits[:20])
            addendum = "\n".join(filter(None, addendum_lines)) + "\n"
            new_text = text[:insert_pos].rstrip() + "\n" + addendum + "\n" + text[insert_pos:]
        else:
            # start を呼ばずに end が来た — 新規 section + end まとめて書く
            commits = get_recent_commits(log_path.parent, None)
            block = [
                f"\n## {uuid_short} {date}",
                f"- end-only: {iso_now}",
                f"- summary: {args.summary}" if args.summary else "",
            ]
            if commits:
                block.append("- commits:")
                block.extend(f"  - {c}" for c in commits[:20])
            new_text = text.rstrip() + "\n" + "\n".join(filter(None, block)) + "\n"
        action_desc = f"end {uuid_short}"

    if args.dry:
        print(f"[dry] would update {log_path}")
        print(f"action: {action_desc}")
        # diff 風
        diff_lines = [
            l for l in new_text.splitlines()[-15:]
        ]
        print("--- tail preview ---")
        for l in diff_lines:
            print(l)
        return 0

    log_path.write_text(new_text, encoding="utf-8")
    rotate_if_large(log_path)
    print(f"✅ {action_desc}  -> {log_path}")
    logger.done(TOOL_ID, action_desc, pj=args.pj)
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
