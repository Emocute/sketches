#!/usr/bin/env python3
"""chord-forge — 唸るコード進行を量産して Pianoteq で鳴らす。

Studio の和声エンジン (harmony_utils) を総動員する。
度数カタログ → ボイスリーディング最適化 → MIDI → Pianoteq WAV → index.html。

  python3 forge.py list
  python3 forge.py all                       # 全カタログ make+render+page+open
  python3 forge.py make --id marunouchi --key F
  python3 forge.py make --reharm             # Studio 変換でリハーモ版も増殖
  python3 forge.py render                     # 既存 MIDI を Pianoteq でレンダ
  python3 forge.py page                       # index.html を再生成
"""

import sys
import os
import struct
import random
import argparse
import subprocess
import html
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDIO_TOOLS = HERE.parent.parent / "Studio" / "tools"
if not STUDIO_TOOLS.exists():
    raise SystemExit(f"[forge] Studio 和声エンジンが見つからない: {STUDIO_TOOLS}")
sys.path.insert(0, str(STUDIO_TOOLS))
import harmony_utils as H  # noqa: E402

MIDI_DIR = HERE / "midi"
WAV_DIR = HERE / "wav"
PIANOTEQ = "/Applications/Pianoteq 9/Pianoteq 9.app/Contents/MacOS/Pianoteq 9"
DEFAULT_PRESET = "NY Steinway D Jazz"
PPQ = 480

# 度数(半音)→名前。メジャースケール準拠 (I=0..VII=11) + 借用
DEG_NAME = {0: "I", 1: "bII", 2: "II", 3: "bIII", 4: "III", 5: "IV",
            6: "bV", 7: "V", 8: "bVI", 9: "VI", 10: "bVII", 11: "VII"}

# ─────────────────────────────────────────────
# カタログ — (半音offset, quality, roman表示) の列。tonic からの相対。
# quality は harmony_utils._CHORD_QUALITY_INTERVALS のキーに限る（起動時に検証）。
# ─────────────────────────────────────────────
def C(deg, q, label=None):
    return (deg, q, label or (DEG_NAME[deg % 12] + ("" if q in ("maj", "") else q)))

CATALOG = [
    # ── 邦楽王道・循環系 ───────────────────────────────
    dict(id="royal_road", name="王道進行 4536", mode="major", default_key="C",
         tag="J-POP 王道", bpm=78,
         note="IVM7→V7→IIIm7→VIm7。緊張(IV)→解決予感(V)→翳り(IIIm)→着地(VIm)。"
              "サビ定番。後半を IIm7-V7 でターンバックさせて 8 コードに。",
         chords=[C(5,"maj7"),C(7,"9"),C(4,"m7"),C(9,"m7"),
                 C(5,"maj7"),C(7,"9"),C(2,"m7"),C(7,"9")]),
    dict(id="marunouchi", name="丸の内サディスティック / 丸サ進行", mode="major", default_key="F",
         tag="シティポップ循環", bpm=92,
         note="IVM7→III7→VIm7→I7 の循環。III7 がセカンダリドミナントで VIm へ強く引っ張る。"
              "I7 が次の IV への裏の推進力（=丸サの粘り）。",
         chords=[C(5,"maj7"),C(4,"7"),C(9,"m9"),C(0,"7"),
                 C(5,"maj7"),C(4,"7"),C(9,"m9"),C(0,"9")]),
    dict(id="just_two_of_us", name="Just the Two of Us 進行", mode="major", default_key="C",
         tag="ネオソウル循環", bpm=84,
         note="丸サの祖型。IVM9→III7→VIm9→(I7) の下行。テンションを 9th まで盛って黒っぽく。",
         chords=[C(5,"maj9"),C(4,"7b9"),C(9,"m9"),C(2,"m9"),
                 C(7,"9"),C(0,"maj9"),C(5,"maj9"),C(7,"7b9")]),
    dict(id="komuro", name="小室進行 VIm-IV-V-I", mode="major", default_key="A",
         tag="90s 疾走", bpm=140,
         note="VIm→IV→V→I。短調的な出だしから長調 I へ抜ける高揚。J-POP の DNA。"
              "ここでは 7th を足してベタ化を回避。",
         chords=[C(9,"m7"),C(5,"maj7"),C(7,"9"),C(0,"maj7"),
                 C(9,"m7"),C(5,"maj7"),C(7,"9"),C(0,"6/9")]),
    dict(id="canon", name="カノン進行", mode="major", default_key="D",
         tag="鉄板下行", bpm=72,
         note="I-V-VIm-IIIm-IV-I-IV-V。バスが順次下行する黄金線。"
              "IIIm を III7 にすると一気に泣ける（reharm 版参照）。",
         chords=[C(0,"maj7"),C(7,"9"),C(9,"m7"),C(4,"m7"),
                 C(5,"maj7"),C(0,"maj7"),C(5,"maj7"),C(7,"9")]),

    # ── ジャズ・リハーモ系 ─────────────────────────────
    dict(id="coltrane", name="Coltrane Changes (Giant Steps)", mode="major", default_key="C",
         tag="長3度サイクル", bpm=96,
         note="長3度で 3 分割した転調サイクル。Imaj7→bIII7→bVImaj7→VII7→IIImaj7→V7→Imaj7。"
              "各 maj7 へ直前のドミナントが解決し続ける目眩。",
         chords=[C(0,"maj7"),C(3,"7"),C(8,"maj7"),C(11,"7"),
                 C(4,"maj7"),C(7,"7"),C(0,"maj7"),C(7,"7")]),
    dict(id="backdoor", name="バックドア II-V", mode="major", default_key="C",
         tag="裏口解決", bpm=88,
         note="Imaj7→VIm7→IIm7→bVII7→Imaj7。bVII7(=借用ドミナント)が"
              "正規 V7 を通らず裏口から I へ落ちる。柔らかい解決感。",
         chords=[C(0,"maj9"),C(9,"m7"),C(2,"m9"),C(10,"9"),
                 C(0,"maj9"),C(9,"m7"),C(2,"m7"),C(10,"7")]),
    dict(id="tritone_turnaround", name="裏コード・ターンアラウンド", mode="major", default_key="C",
         tag="トライトーン置換", bpm=90,
         note="Imaj7→bIII7→bVImaj7→bII7。全ドミナントを裏コードに置換した半音下行ターンバック。"
              "ルートが半音ずつ滑り落ちる。",
         chords=[C(0,"maj7"),C(3,"7#9"),C(8,"maj7"),C(1,"7#9"),
                 C(0,"maj7"),C(3,"7#9"),C(8,"maj7"),C(1,"7b9")]),
    dict(id="ii_v_chain", name="II-V 連鎖（循環半音下行）", mode="major", default_key="C",
         tag="ジャズ循環", bpm=100,
         note="IIIm7-VI7 / IIm7-V7 と II-V を 4 度進行で繋ぎ続ける。"
              "ジャズスタンダードの背骨。最後 Imaj7 で着地。",
         chords=[C(4,"m7"),C(9,"7"),C(2,"m7"),C(7,"7"),
                 C(4,"m7"),C(9,"7"),C(2,"m9"),C(7,"9")]),
    dict(id="rhythm_changes", name="Rhythm Changes ブリッジ", mode="major", default_key="C",
         tag="セカンダリ循環", bpm=120,
         note="III7→VI7→II7→V7。全部ドミナントの 5 度圏連鎖（Sweet Georgia Brown 型）。"
              "解決を引き延ばす推進力の塊。",
         chords=[C(4,"9"),C(9,"7b9"),C(2,"9"),C(7,"7b9"),
                 C(4,"9"),C(9,"7b9"),C(2,"13"),C(7,"7b9")]),

    # ── モーダル・借用系 ───────────────────────────────
    dict(id="aeolian_cadence", name="エオリアン・ケーデンス bVI-bVII-I", mode="major", default_key="C",
         tag="モーダルインターチェンジ", bpm=80,
         note="I→bVImaj7→bVII→I。同主短調から bVI/bVII を借用。"
              "ロック〜アニソンの「上がる」終止。Mr. Children 的高揚。",
         chords=[C(0,"maj7"),C(8,"maj7"),C(10,"maj7"),C(0,"maj7"),
                 C(5,"maj7"),C(8,"maj7"),C(10,"9"),C(0,"6/9")]),
    dict(id="mixolydian_vamp", name="ミクソリディアン・ヴァンプ I-bVII-IV", mode="major", default_key="G",
         tag="モード", bpm=104,
         note="I→bVII→IV→I。bVII で長調の甘さを抜く。ロック/ファンクの土台。"
              "I を 7th にして更にミクソらしく。",
         chords=[C(0,"9"),C(10,"maj7"),C(5,"maj7"),C(0,"9"),
                 C(0,"9"),C(10,"maj7"),C(5,"6/9"),C(7,"7sus4")]),
    dict(id="lydian_float", name="リディアン浮遊 I-II", mode="major", default_key="C",
         tag="#11 の浮遊", bpm=70,
         note="Imaj7→IIM(=#11 を示唆)→Imaj7。長三和音 II が #4 を運び込み無重力化。"
              "久石譲/坂本龍一的な明るい宙づり。",
         chords=[C(0,"maj9"),C(2,"maj7"),C(0,"maj9"),C(2,"maj7"),
                 C(7,"maj7"),C(2,"maj7"),C(0,"6/9"),C(2,"add9")]),
    dict(id="chromatic_mediant", name="クロマティック・メディアント", mode="major", default_key="C",
         tag="非機能的色彩", bpm=66,
         note="Imaj7→bVImaj7→IIImaj7（六音的極）。共通音 1 で繋ぐ非機能進行。"
              "映画的・神秘的な色変化。機能和声を一旦忘れる場所。",
         chords=[C(0,"maj7"),C(8,"maj7"),C(4,"maj7"),C(8,"maj7"),
                 C(0,"maj7"),C(3,"maj7"),C(8,"maj7"),C(0,"maj9")]),

    # ── ラインクリシェ・内声進行 ───────────────────────
    dict(id="line_cliche", name="ラインクリシェ（下行半音内声）", mode="minor", default_key="Am",
         tag="内声半音下行", bpm=68,
         note="Im→ImM7→Im7→Im6。トップ/内声が i→vii→b7→6 と半音で滑り落ちる。"
              "007/ボサノヴァの妖しさ。",
         chords=[C(0,"m"),C(0,"mMaj7"),C(0,"m7"),C(0,"m6"),
                 C(0,"m"),C(0,"mMaj7"),C(0,"m7"),C(0,"m6")]),
    dict(id="my_funny", name="哀愁ライン（My Funny Valentine 型）", mode="minor", default_key="Cm",
         tag="バス下行クリシェ", bpm=64,
         note="Im→ImM7→Im7→IVm7 とバス/内声が i-7-b7-… で下る黄昏線。"
              "マイナーのまま情感を最大化。",
         chords=[C(0,"m"),C(0,"mMaj7"),C(0,"m7"),C(5,"m7"),
                 C(8,"maj7"),C(3,"7"),C(0,"m6"),C(7,"7b9")]),

    # ── 短調・スペイン・ダーク系 ───────────────────────
    dict(id="andalusian", name="アンダルシア終止 Im-bVII-bVI-V", mode="minor", default_key="Am",
         tag="フリジア下行", bpm=96,
         note="Im→bVII→bVI→V。フラメンコの下行四音。V で半音上のフリジア色。"
              "情熱と諦観。最後 V を 7b9 で軋ませる。",
         chords=[C(0,"m"),C(10,"maj7"),C(8,"maj7"),C(7,"7b9"),
                 C(0,"m"),C(10,"maj7"),C(8,"maj7"),C(7,"7#9")]),
    dict(id="phrygian_dom", name="フリジアン・ドミナント（スパニッシュ）", mode="minor", default_key="Em",
         tag="ハーモニックマイナー第5モード", bpm=110,
         note="I7(bII を伴う)→bII→I7。b2 の緊迫。中東〜フラメンコ〜メタルの暗い熱。",
         chords=[C(0,"7b9"),C(1,"maj7"),C(0,"7b9"),C(8,"maj7"),
                 C(0,"7b9"),C(1,"maj7"),C(10,"7"),C(0,"7#9")]),
    dict(id="harmonic_minor_cadence", name="ハーモニックマイナー終止 IVm-V7-Im", mode="minor", default_key="Cm",
         tag="長調 V7 の刺し", bpm=82,
         note="Im→IVm7→V7(b9)→Im。導音を立てた V7 が短調 I に強烈に解決。"
              "クラシック/劇伴の悲劇性。",
         chords=[C(0,"m9"),C(5,"m7"),C(7,"7b9"),C(0,"m9"),
                 C(8,"maj7"),C(5,"m7"),C(7,"7b9"),C(0,"mMaj7")]),
    dict(id="kenny_barron", name="Kenny Barron マイナーヴォイシング", mode="minor", default_key="Cm",
         tag="ネオソウル/モーダル", bpm=76,
         note="Im11 を軸にした左右 5 度積みの揺蕩い。Im11→IVm11→bVIImaj7→bIIImaj7。"
              "解決を急がない夜のピアノ。",
         chords=[C(0,"m11"),C(5,"m11"),C(10,"maj9"),C(3,"maj9"),
                 C(8,"maj7"),C(1,"maj7"),C(0,"m11"),C(7,"7sus4")]),

    # ── ネオソウル・クォータル・現代系 ─────────────────
    dict(id="so_what", name="So What（クォータル/ドリアン）", mode="minor", default_key="Dm",
         tag="4度堆積", bpm=88,
         note="ドリアン上の 4 度積みを半音上げ下げ（Im→bIIm の So What ヴォイシング移動）。"
              "モードジャズの空気。3rd を曖昧にして開く。",
         chords=[C(0,"m11"),C(0,"m11"),C(1,"m11"),C(1,"m11"),
                 C(0,"m11"),C(0,"m11"),C(10,"maj9"),C(0,"m11")]),
    dict(id="neosoul_2536", name="ネオソウル 2-5-3-6（テンション増し）", mode="major", default_key="Eb",
         tag="DAngelo 系", bpm=72,
         note="IIm9→V13→IIImaj7→VIm9 を 9/11/13 で厚く。"
              "拍裏でよれる前提のリッチな循環。",
         chords=[C(2,"m9"),C(7,"13"),C(4,"m9"),C(9,"m11"),
                 C(2,"m9"),C(7,"7b13"),C(4,"maj7"),C(9,"m9")]),
    dict(id="picardy", name="ピカルディ終止（短→長で締める）", mode="minor", default_key="Am",
         tag="長三和音の救済", bpm=70,
         note="短調進行の最後を I（長三和音）で締める。Im→IVm→V7→Imaj。"
              "翳りからの一筋の光。",
         chords=[C(0,"m9"),C(5,"m7"),C(7,"7b9"),C(0,"maj7"),
                 C(8,"maj7"),C(5,"m7"),C(7,"7b9"),C(0,"6/9")]),
    dict(id="passing_dim", name="パッシングディミニッシュ上行", mode="major", default_key="C",
         tag="経過減和音", bpm=98,
         note="I→#Idim→IIm7→#IIdim→IIIm7。半音上行を減和音で繋ぐ古典の常套。"
              "ラグタイム/シティポップの滑らかな上昇。",
         chords=[C(0,"maj7"),C(1,"dim7"),C(2,"m7"),C(3,"dim7"),
                 C(4,"m7"),C(7,"9"),C(0,"maj7"),C(7,"7b9")]),
    dict(id="omori", name="切ない循環 IV-V-IIIm-VIm（おもひで型）", mode="major", default_key="D",
         tag="J-POP 哀愁", bpm=86,
         note="IVM7→V7→IIIm7→VIm7 を 9th 多めで。王道の親戚だが頭が IV で始まる漂い。"
              "夕方の質感。",
         chords=[C(5,"maj9"),C(7,"9"),C(4,"m7"),C(9,"m9"),
                 C(2,"m9"),C(7,"9"),C(0,"maj9"),C(9,"m7")]),
    dict(id="hexatonic_pop", name="長三和音の極移動（神秘和音）", mode="major", default_key="C",
         tag="非機能トライアド", bpm=60,
         note="Imaj→bVImaj→bIIImaj→… 長三和音だけを 1 共通音で渡る。"
              "ホルスト/ヒーリング系の浮揚。",
         chords=[C(0,"add9"),C(8,"add9"),C(3,"add9"),C(8,"add9"),
                 C(0,"add9"),C(4,"add9"),C(9,"add9"),C(0,"6/9")]),
]

CATALOG_BY_ID = {e["id"]: e for e in CATALOG}


# ─────────────────────────────────────────────
# 検証 — quality がエンジンの辞書に存在するか
# ─────────────────────────────────────────────
def validate_catalog():
    valid = set(H._CHORD_QUALITY_INTERVALS.keys())
    bad = []
    for e in CATALOG:
        for deg, q, label in e["chords"]:
            if q not in valid:
                bad.append((e["id"], q))
    if bad:
        raise SystemExit(f"[forge] 未知の quality: {bad}\n使える: {sorted(valid)}")


# ─────────────────────────────────────────────
# 進行 → ボイシング（Studio エンジン総動員）
# ─────────────────────────────────────────────
def chords_to_voicings(entry, key, max_voices=5):
    """カタログ entry を MIDI ボイシング列に。auto_voice_lead でなめらかに。"""
    tonic_pc = H.parse_key(key)[0]
    prog = [((tonic_pc + deg) % 12, q) for deg, q, _ in entry["chords"]]
    voicings = H.auto_voice_lead(prog, start_octave=4, max_voices=max_voices)
    # ルートベースを 1 本下に足す
    roots = []
    for deg, q, _ in entry["chords"]:
        bass = 36 + ((tonic_pc + deg) % 12)  # 低めの C(36) 帯
        roots.append(bass)
    return voicings, roots


# ─────────────────────────────────────────────
# SMF type-0 ライタ（依存ゼロ）
# ─────────────────────────────────────────────
def _vlq(n):
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def render_events(voicings, roots, style, bpm, beats_per_chord, loops, seed=0):
    """(abs_tick, status, note, vel) の列を作る。"""
    rnd = random.Random(seed)
    chord_ticks = int(PPQ * beats_per_chord)
    evs = []
    t0 = 0
    for _ in range(loops):
        for ci, (chord, root) in enumerate(zip(voicings, roots)):
            notes = sorted(set(chord))
            top = max(notes) if notes else 0
            # ベース + コード本体
            voice_notes = [root] + notes
            n = len(voice_notes)
            for vi, pitch in enumerate(voice_notes):
                if style == "block":
                    on = t0
                elif style == "rolled":
                    # 下から上へ軽くロール（人間味）
                    on = t0 + int(vi * (PPQ * 0.018)) + rnd.randint(0, 6)
                elif style == "arp":
                    step = chord_ticks // max(n, 1)
                    on = t0 + vi * step
                else:
                    on = t0
                # ベロシティ: ベース太め、トップ少し立てる、中間柔らか
                if pitch == root:
                    vel = 74
                elif pitch == top:
                    vel = 82
                else:
                    vel = 60 + rnd.randint(-4, 6)
                if style == "arp":
                    off = on + step - 6
                else:
                    off = t0 + chord_ticks - int(PPQ * 0.06)  # 軽くデタッシェ
                off = max(off, on + 30)
                evs.append((on, 0x90, pitch, vel))
                evs.append((off, 0x80, pitch, 0))
            t0 += chord_ticks
    return evs


def write_midi(path, evs, bpm):
    # トラックデータ
    track = bytearray()
    # テンポ
    mpqn = int(60_000_000 / bpm)
    track += _vlq(0) + bytes([0xFF, 0x51, 0x03]) + mpqn.to_bytes(3, "big")
    # プログラム = Acoustic Grand Piano(0)
    track += _vlq(0) + bytes([0xC0, 0])
    evs = sorted(evs, key=lambda e: (e[0], 0 if e[1] == 0x80 else 1))
    last = 0
    for tick, status, note, vel in evs:
        delta = tick - last
        last = tick
        track += _vlq(delta) + bytes([status, note & 0x7F, vel & 0x7F])
    track += _vlq(0) + bytes([0xFF, 0x2F, 0x00])  # end of track
    # ヘッダ
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, PPQ)
    chunk = b"MTrk" + struct.pack(">I", len(track)) + bytes(track)
    path.write_bytes(header + chunk)


# ─────────────────────────────────────────────
# make / render / page
# ─────────────────────────────────────────────
def make_one(entry, key, style, bpm, loops):
    voicings, roots = chords_to_voicings(entry, key)
    evs = render_events(voicings, roots, style, bpm, beats_per_chord=2, loops=loops)
    stem = f"{entry['id']}_{key.replace('#','s')}"
    midi_path = MIDI_DIR / f"{stem}.mid"
    write_midi(midi_path, evs, bpm)
    return stem, midi_path


def reharm_variants(entry, key):
    """Studio の変換でリハーモ版を増殖（セカンダリドミナント挿入 / 裏コード置換）。"""
    tonic_pc = H.parse_key(key)[0]
    prog = [((tonic_pc + deg) % 12, q) for deg, q, _ in entry["chords"]]
    out = []
    try:
        sd = H.insert_secondary_dominants(prog)
        if sd and sd != prog:
            out.append(("secdom", sd))
    except Exception:
        pass
    try:
        tts = H.generate_tritone_substitutions(prog)
        if tts:
            sub = list(prog)
            for item in tts:
                idx = item.get("position") if isinstance(item, dict) else None
                newc = item.get("substitute_pc") if isinstance(item, dict) else None
                if idx is not None and newc is not None and 0 <= idx < len(sub):
                    sub[idx] = (newc % 12, "7#9")
            if sub != prog:
                out.append(("tritone", sub))
    except Exception:
        pass
    return out


def make_reharm_one(entry, key, variant_tag, prog, style, bpm, loops):
    voicings = H.auto_voice_lead(prog, start_octave=4, max_voices=5)
    roots = [36 + (pc % 12) for pc, q in prog]
    evs = render_events(voicings, roots, style, bpm, beats_per_chord=2, loops=loops)
    stem = f"{entry['id']}_{key.replace('#','s')}_{variant_tag}"
    midi_path = MIDI_DIR / f"{stem}.mid"
    write_midi(midi_path, evs, bpm)
    return stem, midi_path


def render_wav(midi_path, preset):
    if not Path(PIANOTEQ).exists():
        return None, "Pianoteq 9 が見つからない"
    wav_path = WAV_DIR / (midi_path.stem + ".wav")
    cmd = [PIANOTEQ, "--headless", "--preset", preset,
           "--midi", str(midi_path), "--wav", str(wav_path),
           "--rate", "44100", "--quiet"]
    try:
        subprocess.run(cmd, check=True, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return wav_path, None
    except Exception as ex:
        return None, str(ex)


def chord_labels(entry):
    return " → ".join(lbl for _, _, lbl in entry["chords"])


def build_page(items, preset):
    """items: list of dict(id,name,tag,note,labels,wav,bpm,key)。<audio preload=none>."""
    rows = []
    for it in items:
        wav_rel = ("wav/" + Path(it["wav"]).name) if it.get("wav") else None
        audio = (f'<audio controls preload="none" src="{html.escape(wav_rel)}"></audio>'
                 if wav_rel else '<span class="nowav">WAV 未生成</span>')
        rows.append(f"""
    <article>
      <header><h2>{html.escape(it['name'])}</h2>
        <span class="tag">{html.escape(it['tag'])}</span>
        <span class="meta">key {html.escape(it['key'])} · {it['bpm']} BPM</span>
      </header>
      <p class="prog">{html.escape(it['labels'])}</p>
      <p class="note">{html.escape(it['note'])}</p>
      {audio}
    </article>""")
    body = "\n".join(rows)
    doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chord Forge — 唸る進行</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ background:#0d0e12; color:#e7e7ea; font-family:-apple-system,"Hiragino Kaku Gothic ProN",sans-serif;
         margin:0; padding:32px 18px 80px; }}
  h1 {{ font-size:20px; font-weight:600; letter-spacing:.04em; margin:0 0 4px; }}
  .sub {{ color:#8a8d99; font-size:12px; margin:0 0 28px; }}
  article {{ background:#15171e; border:1px solid #23262f; border-radius:12px;
            padding:16px 18px; margin:0 auto 14px; max-width:760px; }}
  header {{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }}
  h2 {{ font-size:15px; font-weight:600; margin:0; }}
  .tag {{ font-size:11px; color:#0d0e12; background:#9fd0ff; border-radius:5px; padding:1px 7px; }}
  .meta {{ font-size:11px; color:#7c8090; }}
  .prog {{ font-family:"SF Mono",ui-monospace,monospace; font-size:13px; color:#ffd9a0;
          margin:10px 0 6px; letter-spacing:.02em; }}
  .note {{ font-size:12px; color:#aeb2bf; line-height:1.6; margin:0 0 12px; }}
  audio {{ width:100%; height:34px; }}
  .nowav {{ font-size:12px; color:#6a6e7a; }}
</style></head><body>
  <h1>Chord Forge</h1>
  <p class="sub">Studio 和声エンジン総動員 · Pianoteq「{html.escape(preset)}」· {len(items)} progressions</p>
  {body}
</body></html>"""
    out = HERE / "index.html"
    out.write_text(doc, encoding="utf-8")
    return out


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def cmd_list(_args):
    print(f"{'ID':<22}{'技法':<24}{'進行'}")
    print("─" * 100)
    for e in CATALOG:
        print(f"{e['id']:<22}{e['tag']:<22}{chord_labels(e)}")
    print(f"\n計 {len(CATALOG)} progressions")


def collect(ids):
    if not ids:
        return CATALOG
    sel = []
    for i in ids:
        if i not in CATALOG_BY_ID:
            raise SystemExit(f"[forge] 未知の id: {i}")
        sel.append(CATALOG_BY_ID[i])
    return sel


def cmd_make(args):
    validate_catalog()
    entries = collect(args.id)
    items = []
    for e in entries:
        key = args.key or e["default_key"]
        bpm = args.bpm or e["bpm"]
        stem, midi = make_one(e, key, args.style, bpm, args.loops)
        wav = None
        if args.render:
            wav, err = render_wav(midi, args.preset)
            if err:
                print(f"  ! {stem}: {err}")
        items.append(dict(id=e["id"], name=e["name"], tag=e["tag"], note=e["note"],
                          labels=chord_labels(e), wav=str(wav) if wav else None,
                          bpm=bpm, key=key))
        print(f"  ✓ {stem}.mid" + (f"  → {Path(wav).name}" if wav else ""))
        # reharm 増殖
        if args.reharm:
            for vtag, prog in reharm_variants(e, key):
                rstem, rmidi = make_reharm_one(e, key, vtag, prog, args.style, bpm, args.loops)
                rwav = None
                if args.render:
                    rwav, _ = render_wav(rmidi, args.preset)
                labels = " → ".join(
                    DEG_NAME[(pc - H.parse_key(key)[0]) % 12] + (q if q != "maj" else "")
                    for pc, q in prog)
                items.append(dict(id=f"{e['id']}_{vtag}", name=f"{e['name']}〔{vtag}〕",
                                  tag=f"{e['tag']} / reharm", note=f"{e['note']}（{vtag} 変換版）",
                                  labels=labels, wav=str(rwav) if rwav else None,
                                  bpm=bpm, key=key))
                print(f"    ↳ {rstem}.mid" + (f"  → {Path(rwav).name}" if rwav else ""))
    page = build_page(items, args.preset)
    print(f"\nindex.html: {page}")
    if args.open:
        _open_page(page)
    return items


def cmd_render(args):
    midis = sorted(MIDI_DIR.glob("*.mid"))
    if not midis:
        raise SystemExit("[forge] midi/ が空。先に make を。")
    for m in midis:
        wav, err = render_wav(m, args.preset)
        print(f"  {'✓' if wav else '!'} {m.stem}" + (f"  {err}" if err else ""))
    print("WAV →", WAV_DIR)


def cmd_page(args):
    # 既存 wav を index.html に並べ直す（カタログ照合）
    items = []
    for e in CATALOG:
        for w in sorted(WAV_DIR.glob(f"{e['id']}_*.wav")):
            items.append(dict(id=e["id"], name=e["name"], tag=e["tag"], note=e["note"],
                              labels=chord_labels(e), wav=str(w),
                              bpm=e["bpm"], key=e["default_key"]))
    page = build_page(items, args.preset)
    print("index.html:", page)
    if args.open:
        _open_page(page)


def cmd_all(args):
    args.id = []
    args.render = True
    args.open = True
    cmd_make(args)


def _open_page(page):
    subprocess.run(["open", "-na", "Google Chrome", "--args",
                    "--new-window", str(page)], check=False)


def main():
    ap = argparse.ArgumentParser(description="chord-forge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--key", help="キー (例 C, F, Am, Ebm)。省略=進行ごとの既定")
        p.add_argument("--bpm", type=int, help="BPM。省略=進行ごとの既定")
        p.add_argument("--style", choices=["block", "rolled", "arp"], default="rolled")
        p.add_argument("--loops", type=int, default=2, help="進行を何周鳴らすか")
        p.add_argument("--preset", default=DEFAULT_PRESET, help="Pianoteq プリセット")

    pl = sub.add_parser("list"); pl.set_defaults(func=cmd_list)

    pm = sub.add_parser("make"); common(pm)
    pm.add_argument("--id", nargs="*", default=[], help="特定 id だけ（省略=全部）")
    pm.add_argument("--reharm", action="store_true", help="Studio 変換でリハーモ版も増殖")
    pm.add_argument("--render", action="store_true", help="Pianoteq で WAV も書く")
    pm.add_argument("--open", action="store_true", help="index.html を Chrome で開く")
    pm.set_defaults(func=cmd_make)

    pr = sub.add_parser("render"); pr.add_argument("--preset", default=DEFAULT_PRESET)
    pr.set_defaults(func=cmd_render)

    pp = sub.add_parser("page")
    pp.add_argument("--preset", default=DEFAULT_PRESET)
    pp.add_argument("--open", action="store_true")
    pp.set_defaults(func=cmd_page)

    pa = sub.add_parser("all"); common(pa)
    pa.add_argument("--reharm", action="store_true")
    pa.set_defaults(func=cmd_all)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
