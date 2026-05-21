#!/usr/bin/env python3
"""Lydian × geometric MIDI generators.

Writes Standard MIDI File (SMF type 0) bytes directly — no external deps.
Output goes to ../output/.

Five patterns:
  1. lydian_tonnetz.mid              — Lydian-tinted triad progression via Tonnetz voice leading
  2. lydian_lcc_stack.mid            — George Russell's LCC 5th-stack accumulation
  3. lydian_wholetone_mirror.mid     — Mirrored Lydian arpeggio (axis of symmetry)
  4. lydian_spectral.mid             — Harmonic series partials with #11 overtone stack finale
  5. lydian_fibonacci.mid            — Lydian notes at Fibonacci-spaced time positions
"""

from __future__ import annotations

import math
from pathlib import Path

TICKS_PER_BEAT = 480
BPM = 100

# C Lydian: C D E F# G A B
LYDIAN_INTERVALS = [0, 2, 4, 6, 7, 9, 11]


# ----------------------------------------------------------------------------
# SMF byte writer
# ----------------------------------------------------------------------------

def vlq(n: int) -> bytes:
    if n == 0:
        return b"\x00"
    parts: list[int] = []
    while n > 0:
        parts.append(n & 0x7F)
        n >>= 7
    parts.reverse()
    out = bytearray()
    for i, p in enumerate(parts):
        out.append(p | 0x80 if i < len(parts) - 1 else p)
    return bytes(out)


def note_on(ch: int, note: int, vel: int) -> bytes:
    return bytes([0x90 | (ch & 0x0F), note & 0x7F, vel & 0x7F])


def note_off(ch: int, note: int) -> bytes:
    return bytes([0x80 | (ch & 0x0F), note & 0x7F, 0])


def meta_tempo(bpm: float) -> bytes:
    us_per_quarter = int(60_000_000 / bpm)
    return b"\xff\x51\x03" + us_per_quarter.to_bytes(3, "big")


def meta_time_sig(num: int = 4, den_pow: int = 2) -> bytes:
    return b"\xff\x58\x04" + bytes([num, den_pow, 24, 8])


def meta_track_name(name: str) -> bytes:
    data = name.encode("utf-8")
    return b"\xff\x03" + vlq(len(data)) + data


def meta_eot() -> bytes:
    return b"\xff\x2f\x00"


def write_smf(path: Path, events: list[tuple[int, bytes]], name: str) -> None:
    track_data = bytearray()
    # Meta at tick 0
    track_data += vlq(0) + meta_track_name(name)
    track_data += vlq(0) + meta_tempo(BPM)
    track_data += vlq(0) + meta_time_sig()
    # Sort events by tick (stable for same-tick to keep NoteOff before NoteOn)
    # Convention: NoteOff (0x80..0x8F) should fire before NoteOn at the same tick
    def sort_key(ev: tuple[int, bytes]) -> tuple[int, int]:
        return (ev[0], 0 if (ev[1][0] & 0xF0) == 0x80 else 1)
    events_sorted = sorted(events, key=sort_key)
    prev_tick = 0
    for abs_tick, ev in events_sorted:
        delta = abs_tick - prev_tick
        track_data += vlq(delta) + ev
        prev_tick = abs_tick
    track_data += vlq(0) + meta_eot()

    header = (
        b"MThd"
        + (6).to_bytes(4, "big")
        + (0).to_bytes(2, "big")
        + (1).to_bytes(2, "big")
        + TICKS_PER_BEAT.to_bytes(2, "big")
    )
    track = b"MTrk" + len(track_data).to_bytes(4, "big") + bytes(track_data)
    path.write_bytes(header + track)


# ----------------------------------------------------------------------------
# Pattern 1: Lydian Tonnetz
# ----------------------------------------------------------------------------

def gen_lydian_tonnetz(root_midi: int = 60) -> list[tuple[int, bytes]]:
    """Lydian diatonic triads in a Tonnetz-style smooth voice-leading path.

    C Lydian triads: I=Cmaj, II=Dmaj (Lydian signature), iii=Em, V=Gmaj,
    vi=Am, vii°=Bdim. Path emphasizes common-tone retention.
    """
    # (intervals from C, voicing relative to C4 with smooth voice leading)
    # Each chord lasts 2 beats; total 16 chords = 8 bars
    progression = [
        ("Cmaj",  [60, 64, 67]),  # I
        ("Em",    [59, 64, 67]),  # iii (shares E, G with Cmaj; B is new)
        ("Am",    [60, 64, 69]),  # vi (shares C, E)
        ("Dmaj",  [62, 66, 69]),  # II (Lydian signature — F# enters)
        ("Gmaj",  [62, 67, 71]),  # V (shares D)
        ("Bdim",  [62, 65, 71]),  # vii° (shares D, B)
        ("Em",    [64, 67, 71]),  # iii (shares E, G, B)
        ("Am",    [64, 69, 72]),  # vi
        ("Dmaj",  [66, 69, 74]),  # II
        ("Gmaj",  [67, 71, 74]),  # V
        ("Cmaj",  [67, 72, 76]),  # I (high voicing)
        ("Gmaj",  [67, 71, 74]),  # V
        ("Dmaj",  [66, 69, 74]),  # II
        ("Am",    [64, 69, 72]),  # vi
        ("Em",    [64, 67, 71]),  # iii
        ("Cmaj",  [60, 64, 67]),  # I (return)
    ]
    events: list[tuple[int, bytes]] = []
    chord_ticks = 2 * TICKS_PER_BEAT
    for i, (_name, notes) in enumerate(progression):
        start = i * chord_ticks
        end = start + chord_ticks
        for n in notes:
            events.append((start, note_on(0, n, 78)))
            events.append((end - 5, note_off(0, n)))
    return events


# ----------------------------------------------------------------------------
# Pattern 2: LCC 5th-stack accumulation
# ----------------------------------------------------------------------------

def gen_lydian_lcc_stack(root_midi: int = 48) -> list[tuple[int, bytes]]:
    """Build the Lydian scale as a 7-note 5th-stack, one voice per bar.

    Bar 1: C only.  Bar 2: + G.  Bar 3: + D.  ...  Bar 7: + F# (full Lydian).
    Bar 8: all sustained.
    """
    voices = [root_midi + 7 * i for i in range(7)]
    # voices: 48 (C2), 55 (G2), 62 (D3), 69 (A3), 76 (E4), 83 (B4), 90 (F#5)
    events: list[tuple[int, bytes]] = []
    bar = 4 * TICKS_PER_BEAT
    end_tick = 8 * bar
    for i, n in enumerate(voices):
        start = i * bar
        events.append((start, note_on(0, n, 60 + i * 6)))
        events.append((end_tick - 5, note_off(0, n)))
    return events


# ----------------------------------------------------------------------------
# Pattern 3: Whole-tone mirror (axis of symmetry on F#)
# ----------------------------------------------------------------------------

def gen_lydian_wholetone_mirror(root_midi: int = 60) -> list[tuple[int, bytes]]:
    """Ascending Lydian 8th-notes in mid octave, descending mirror image two octaves up.

    Mirror axis = F#5 (78). Each pair is geometrically symmetric around this axis.
    Lydian's #4 = F# is itself the symmetry axis → Lydian is the only diatonic mode
    whose pitch-class set is symmetric about its #4.
    """
    # Ascending Lydian, 2 octaves (14 notes)
    asc = [root_midi + i for i in LYDIAN_INTERVALS] + [
        root_midi + 12 + i for i in LYDIAN_INTERVALS
    ]
    axis = 78  # F#5
    # Mirror: descending shape symmetric around axis
    desc = [2 * axis - n for n in asc]

    events: list[tuple[int, bytes]] = []
    eighth = TICKS_PER_BEAT // 2
    note_len = eighth - 10
    # 4 bars (32 eighths) — loop 14-note shape ~2.3 times
    for i in range(32):
        nu = asc[i % len(asc)]
        nd = desc[i % len(desc)]
        t = i * eighth
        events.append((t, note_on(0, nu, 78)))
        events.append((t + note_len, note_off(0, nu)))
        events.append((t, note_on(0, nd, 70)))
        events.append((t + note_len, note_off(0, nd)))
    return events


# ----------------------------------------------------------------------------
# Pattern 4: Spectral (harmonic series)
# ----------------------------------------------------------------------------

def gen_lydian_spectral(root_midi: int = 36) -> list[tuple[int, bytes]]:
    """Arpeggio of partials 1..16, then a sustained overtone stack including the 11th.

    The 11th harmonic ≈ #11 above the fundamental → physical origin of Lydian.
    Partial k → root + round(12 * log2(k)) semitones.
    """
    events: list[tuple[int, bytes]] = []
    eighth = TICKS_PER_BEAT // 2
    note_len = eighth - 20

    t = 0
    for k in range(1, 17):
        st = round(12 * math.log2(k))
        n = root_midi + st
        vel = 60 + min(40, k * 3)
        events.append((t, note_on(0, n, vel)))
        events.append((t + note_len, note_off(0, n)))
        t += eighth

    # Final stack — partials 1,2,3,4,5,6,8,11 (Lydian #11 voicing)
    stack_partials = [1, 2, 3, 4, 5, 6, 8, 11]
    stack_notes = [root_midi + round(12 * math.log2(p)) for p in stack_partials]
    stack_dur = 8 * TICKS_PER_BEAT  # 8 beats
    for n in stack_notes:
        events.append((t, note_on(0, n, 75)))
        events.append((t + stack_dur, note_off(0, n)))
    return events


# ----------------------------------------------------------------------------
# Pattern 5: Fibonacci timing
# ----------------------------------------------------------------------------

def gen_lydian_fibonacci(root_midi: int = 60) -> list[tuple[int, bytes]]:
    """Lydian scale notes placed at Fibonacci-spaced 8th-note positions.

    Δt (in 8ths): 1, 1, 2, 3, 5, 8, 13, 21, 34, 55
    Sustained notes overlap → growing harmonic field as Fibonacci ratios → φ-resonance.
    """
    fib = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
    cum: list[int] = []
    s = 0
    for f in fib:
        cum.append(s)
        s += f

    # 12 Lydian notes ascending across 2 octaves
    scale = [root_midi + i for i in LYDIAN_INTERVALS] + [
        root_midi + 12 + i for i in LYDIAN_INTERVALS[:5]
    ]

    events: list[tuple[int, bytes]] = []
    eighth = TICKS_PER_BEAT // 2
    # Each note sustains 4 beats (overlapping field)
    sustain = 4 * TICKS_PER_BEAT
    for i, c in enumerate(cum):
        t = c * eighth
        n = scale[i % len(scale)]
        vel = 70 + (i * 3) % 30
        events.append((t, note_on(0, n, vel)))
        events.append((t + sustain, note_off(0, n)))
    return events


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main() -> None:
    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    patterns = [
        ("lydian_tonnetz.mid",          "Lydian Tonnetz",          gen_lydian_tonnetz()),
        ("lydian_lcc_stack.mid",        "Lydian LCC Stack",        gen_lydian_lcc_stack()),
        ("lydian_wholetone_mirror.mid", "Lydian Wholetone Mirror", gen_lydian_wholetone_mirror()),
        ("lydian_spectral.mid",         "Lydian Spectral",         gen_lydian_spectral()),
        ("lydian_fibonacci.mid",        "Lydian Fibonacci",        gen_lydian_fibonacci()),
    ]
    print(f"BPM={BPM}, ticks/beat={TICKS_PER_BEAT}")
    print(f"Output: {out_dir}/")
    for filename, name, events in patterns:
        path = out_dir / filename
        write_smf(path, events, name)
        # Count notes (NoteOn events)
        notes = sum(1 for _, e in events if (e[0] & 0xF0) == 0x90)
        # Last tick
        last_tick = max((t for t, _ in events), default=0)
        bars = last_tick / (4 * TICKS_PER_BEAT)
        print(f"  {filename}: {notes} notes, {bars:.1f} bars")


if __name__ == "__main__":
    main()
