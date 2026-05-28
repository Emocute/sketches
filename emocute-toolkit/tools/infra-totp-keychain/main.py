"""infra-totp-keychain — keychain 保存の TOTP secret から code 生成.

Google Authenticator 互換 (HMAC-SHA1, 6 digit, 30s window)。
2FA 要求時に CLI 一発でコピペ可能なコードを表示。
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import hmac
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "infra-totp-keychain"
KEYCHAIN_SVC = "emocute-totp"


def totp(secret_b32: str, t: int | None = None, digits: int = 6, period: int = 30) -> str:
    key = base64.b32decode(secret_b32.replace(" ", "").upper() + "=" * (-len(secret_b32) % 8))
    counter = (t or int(time.time())) // period
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[-1] & 0x0F
    code = (struct.unpack(">I", h[o:o+4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def kc_set(label: str, secret: str) -> None:
    subprocess.run(
        ["security", "add-generic-password", "-U", "-s", KEYCHAIN_SVC,
         "-a", label, "-w", secret], check=True, capture_output=True)


def kc_get(label: str) -> str | None:
    r = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SVC, "-a", label, "-w"],
        capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute infra totp-keychain")
    sub = p.add_subparsers(dest="action", required=True)
    add = sub.add_parser("add")
    add.add_argument("label"); add.add_argument("secret")
    code = sub.add_parser("code"); code.add_argument("label")
    code.add_argument("--copy", action="store_true", help="pbcopy にコピー")
    return p


def run(args: argparse.Namespace) -> int:
    if args.action == "add":
        kc_set(args.label, args.secret)
        print(f"✅ stored TOTP secret: {args.label}")
        logger.done(TOOL_ID, f"add {args.label}")
        return 0
    if args.action == "code":
        secret = kc_get(args.label)
        if not secret:
            logger.error(TOOL_ID, f"label not found: {args.label}")
            return 2
        code = totp(secret)
        remaining = 30 - (int(time.time()) % 30)
        print(f"{code}  (expires in {remaining}s)")
        if args.copy:
            subprocess.run(["pbcopy"], input=code.encode(), check=False)
            print("  copied to pasteboard")
        logger.done(TOOL_ID, f"code {args.label}")
        return 0
    return 1


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
