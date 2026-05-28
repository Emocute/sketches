"""game-ios-theory-lab-poc — iOS 理論実験室 POC スケルトン生成.

`project_ios_theory_lab_app` 準拠 (構想段階)。SwiftUI スケルトンと
chord-dict.sqlite 同梱想定の Xcode プロジェクト雛形を出力。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "game-ios-theory-lab-poc"

SKELETON = {
    "ContentView.swift": '''import SwiftUI

struct ContentView: View {
    var body: some View {
        Text("Emocute Theory Lab POC")
            .padding()
    }
}
''',
    "TheoryLabApp.swift": '''import SwiftUI

@main
struct TheoryLabApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}
''',
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute game ios-theory-lab-poc")
    p.add_argument("out_dir")
    p.add_argument("--apply", action="store_true")
    return p


def run(args: argparse.Namespace) -> int:
    out = Path(args.out_dir).expanduser().resolve()
    print(f"out:    {out}")
    print(f"files:  {len(SKELETON)}")
    if not args.apply:
        for name in SKELETON:
            print(f"  • {name}")
        print("\n[dry-run]")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    for name, body in SKELETON.items():
        (out / name).write_text(body)
    print(f"✅ wrote {len(SKELETON)} swift files to {out}")
    logger.done(TOOL_ID, "ios theory-lab POC skeleton")
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
