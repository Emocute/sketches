"""studio-audio-fingerprint-dedupe — 重複音源の検出.

ffmpeg で 16kHz mono 化 → 簡易フィンガープリント（4秒チャンクの RMS シーケンス）
で類似度を計算。完全一致だけでなく remaster 違いも検出可能。
"""
from __future__ import annotations
import argparse
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "studio-audio-fingerprint-dedupe"

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute studio audio-fingerprint-dedupe")
    p.add_argument("path", help="ディレクトリ")
    p.add_argument("--chunk-sec", type=float, default=4.0)
    p.add_argument("--threshold", type=float, default=0.95,
                   help="類似度しきい値 (cosine, default 0.95)")
    p.add_argument("--json", action="store_true")
    return p


def fingerprint(path: Path, chunk_sec: float) -> list[float]:
    """16kHz mono PCM 化 → chunk ごと RMS。"""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", str(path),
               "-ac", "1", "-ar", "16000",
               "-f", "s16le", str(tmp_path)]
        r = subprocess.run(cmd, capture_output=True, check=False)
        if r.returncode != 0:
            return []
        data = tmp_path.read_bytes()
        sample_count = len(data) // 2
        chunk_samples = int(16000 * chunk_sec)
        if chunk_samples <= 0 or sample_count == 0:
            return []
        rms_seq = []
        for off in range(0, sample_count - chunk_samples, chunk_samples):
            chunk = data[off * 2: (off + chunk_samples) * 2]
            samples = struct.unpack(f"{chunk_samples}h", chunk)
            mean_sq = sum(s * s for s in samples) / chunk_samples
            rms_seq.append(mean_sq ** 0.5)
        return rms_seq
    finally:
        tmp_path.unlink(missing_ok=True)


def cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    a = a[:n]
    b = b[:n]
    num = sum(x * y for x, y in zip(a, b))
    da = sum(x * x for x in a) ** 0.5
    db = sum(y * y for y in b) ** 0.5
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def run(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        logger.error(TOOL_ID, f"not a dir: {root}")
        return 2

    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS)
    print(f"fingerprinting {len(files)} audio files...")

    fps: list[tuple[Path, list[float]]] = []
    for p in files:
        fp = fingerprint(p, args.chunk_sec)
        if fp:
            fps.append((p, fp))

    pairs = []
    for i in range(len(fps)):
        for j in range(i + 1, len(fps)):
            sim = cosine(fps[i][1], fps[j][1])
            if sim >= args.threshold:
                pairs.append({
                    "a": str(fps[i][0].relative_to(root)),
                    "b": str(fps[j][0].relative_to(root)),
                    "similarity": round(sim, 4),
                    "len_a": len(fps[i][1]),
                    "len_b": len(fps[j][1]),
                })

    pairs.sort(key=lambda x: -x["similarity"])

    if args.json:
        print(json.dumps({"pairs": pairs, "files_analyzed": len(fps)},
                         ensure_ascii=False, indent=2))
    else:
        print(f"\n{len(pairs)} similar pair(s) (sim >= {args.threshold}):")
        for p in pairs[:30]:
            print(f"  {p['similarity']:.4f}  {p['a']}  ≈  {p['b']}")

    logger.done(TOOL_ID, f"analyzed {len(fps)} files, found {len(pairs)} dup candidates")
    return 0 if not pairs else 1


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
