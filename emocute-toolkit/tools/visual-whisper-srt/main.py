"""visual-whisper-srt — 動画/音声から Whisper で SRT 字幕を生成.

whisper-cpp / openai-whisper / whisper.cpp の wrapper。歌詞・トーク両対応。
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "visual-whisper-srt"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute visual whisper-srt")
    p.add_argument("input")
    p.add_argument("--lang", default="ja", help="ISO 言語コード (auto も OK)")
    p.add_argument("--model", default="base", help="whisper モデル名")
    p.add_argument("--backend", choices=["openai", "whisper-cpp"], default="openai")
    p.add_argument("-o", "--out")
    p.add_argument("--apply", action="store_true")
    return p


def run_openai(inp: Path, out_srt: Path, lang: str, model: str) -> int:
    """openai-whisper Python wrapper"""
    try:
        import whisper  # type: ignore
    except ImportError:
        logger.error(TOOL_ID, "pip install openai-whisper")
        return 3
    m = whisper.load_model(model)
    result = m.transcribe(str(inp), language=lang if lang != "auto" else None,
                          word_timestamps=False)
    with open(out_srt, "w") as f:
        for i, seg in enumerate(result["segments"], 1):
            s = seg["start"]; e = seg["end"]
            def fmt(t: float) -> str:
                ms = int((t - int(t)) * 1000)
                t_int = int(t)
                h, t_int = divmod(t_int, 3600)
                m_, s_ = divmod(t_int, 60)
                return f"{h:02d}:{m_:02d}:{s_:02d},{ms:03d}"
            f.write(f"{i}\n{fmt(s)} --> {fmt(e)}\n{seg['text'].strip()}\n\n")
    return 0


def run_cpp(inp: Path, out_srt: Path, lang: str, model: str) -> int:
    if not shutil.which("whisper-cli"):
        logger.error(TOOL_ID, "whisper.cpp not found (brew install whisper-cpp)")
        return 3
    # whisper.cpp は WAV 16k mono が必要
    wav = inp.with_suffix(".whisper.wav")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(inp), "-ar", "16000", "-ac", "1", str(wav)],
                   check=True)
    r = subprocess.run(["whisper-cli", "-f", str(wav), "-l", lang,
                        "-osrt", "-of", str(out_srt.with_suffix("")),
                        "-m", f"/opt/homebrew/share/whisper-cpp/ggml-{model}.bin"],
                       capture_output=True, text=True)
    wav.unlink(missing_ok=True)
    if r.returncode != 0:
        logger.error(TOOL_ID, f"whisper-cli failed: {r.stderr[-300:]}")
        return 3
    return 0


def run(args: argparse.Namespace) -> int:
    inp = Path(args.input).expanduser().resolve()
    if not inp.exists():
        logger.error(TOOL_ID, f"not found: {inp}")
        return 2
    out = Path(args.out).expanduser().resolve() if args.out \
        else inp.with_suffix(".srt")
    print(f"input: {inp.name}  lang: {args.lang}  model: {args.model}  backend: {args.backend}")

    if not args.apply:
        print(f"\n[dry-run] would write: {out}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.backend == "openai":
        rc = run_openai(inp, out, args.lang, args.model)
    else:
        rc = run_cpp(inp, out, args.lang, args.model)
    if rc != 0:
        return rc
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"srt -> {out.name}")
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
