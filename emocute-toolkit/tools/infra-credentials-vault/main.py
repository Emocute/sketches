"""infra-credentials-vault — `~/.config/emocute/credentials.yaml` を keychain 同期.

各種 API キー・PW を macOS Keychain と yaml 間で同期する。
yaml は git-ignored、編集は CLI で fragment 単位。
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "infra-credentials-vault"

DEFAULT_PATH = Path.home() / ".config/emocute/credentials.yaml"
KEYCHAIN_SVC = "emocute-toolkit"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute infra credentials-vault")
    sub = p.add_subparsers(dest="action", required=True)

    sg = sub.add_parser("set"); sg.add_argument("key"); sg.add_argument("value")
    gg = sub.add_parser("get"); gg.add_argument("key")
    ls = sub.add_parser("list")
    dl = sub.add_parser("del"); dl.add_argument("key")
    sub.add_parser("export")  # yaml にダンプ
    sub.add_parser("import")  # yaml から keychain に流し込み
    return p


def kc_set(key: str, value: str) -> None:
    subprocess.run(
        ["security", "add-generic-password", "-U", "-s", KEYCHAIN_SVC,
         "-a", key, "-w", value], check=True, capture_output=True)


def kc_get(key: str) -> str | None:
    r = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SVC,
         "-a", key, "-w"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def kc_del(key: str) -> bool:
    r = subprocess.run(
        ["security", "delete-generic-password", "-s", KEYCHAIN_SVC, "-a", key],
        capture_output=True, text=True)
    return r.returncode == 0


def kc_list() -> list[str]:
    r = subprocess.run(
        ["security", "dump-keychain"], capture_output=True, text=True)
    keys = []
    cur_svc = None
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith('"svce"'):
            cur_svc = line.split('=', 1)[1].strip().strip('"')
        elif line.startswith('"acct"') and cur_svc == KEYCHAIN_SVC:
            acct = line.split('=', 1)[1].strip().strip('"')
            if acct not in keys:
                keys.append(acct)
    return sorted(keys)


def run(args: argparse.Namespace) -> int:
    if args.action == "set":
        kc_set(args.key, args.value)
        print(f"✅ stored {args.key}")
        logger.done(TOOL_ID, f"set {args.key}")
    elif args.action == "get":
        v = kc_get(args.key)
        if v is None:
            print("(not found)")
            return 1
        print(v)
    elif args.action == "list":
        for k in kc_list():
            print(k)
    elif args.action == "del":
        ok = kc_del(args.key)
        print("✅ deleted" if ok else "(not found)")
        return 0 if ok else 1
    elif args.action == "export":
        DEFAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# auto-exported from Keychain. DO NOT COMMIT.\n"]
        for k in kc_list():
            v = kc_get(k) or ""
            v_esc = v.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k}: "{v_esc}"\n')
        DEFAULT_PATH.write_text("".join(lines))
        DEFAULT_PATH.chmod(0o600)
        print(f"✅ exported {len(lines) - 1} keys -> {DEFAULT_PATH}")
    elif args.action == "import":
        if not DEFAULT_PATH.exists():
            logger.error(TOOL_ID, f"yaml not found: {DEFAULT_PATH}")
            return 2
        n = 0
        for line in DEFAULT_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            v = v.strip().strip('"').replace('\\"', '"').replace("\\\\", "\\")
            kc_set(k.strip(), v)
            n += 1
        print(f"✅ imported {n} keys")
        logger.done(TOOL_ID, f"import {n}")
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
