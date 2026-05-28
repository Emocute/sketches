"""env-windows-vm-setup — Windows VM 環境セットアップ手順生成.

VST3/CLAP プラグインの Windows 互換検証用 VM (UTM/Parallels) の
セットアップ手順 md を出力。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "env-windows-vm-setup"

PLAYBOOK = """# Windows VM セットアップ (HarmonyScope プラグイン検証用)

## 前提
- ホスト: macOS (Apple Silicon)
- ハイパーバイザ: UTM (Apple Silicon ネイティブ) もしくは Parallels Desktop
- VM ゲスト: Windows 11 ARM Insider Preview

## セットアップ手順
1. Windows 11 ARM ISO を Microsoft Insider Preview から取得
2. UTM で 4 vCPU / 8GB RAM / 64GB ディスクの VM を作成
3. WinGet 経由で以下をインストール:
   - Visual Studio 2022 Community + C++ workload
   - Rust (rustup-init.exe)
   - Reaper or Cubase LE (VST3 host)
4. clap-validator / pluginval を別途インストール
5. HarmonyScope クロスコンパイル: `rustup target add aarch64-pc-windows-msvc`

## 検証フロー
- `cargo build --release --target aarch64-pc-windows-msvc`
- .vst3 をホスト共有フォルダ経由でゲストへコピー
- pluginval で smoke test
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute env windows-vm-setup")
    p.add_argument("-o", "--out", default="-")
    return p


def run(args: argparse.Namespace) -> int:
    if args.out == "-":
        print(PLAYBOOK)
    else:
        Path(args.out).write_text(PLAYBOOK)
        print(f"✅ wrote {args.out}")
    logger.done(TOOL_ID, "win-vm playbook emitted")
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
