#!/usr/bin/env python3
"""IV Lyd On VI — Lydian slash chord MIDI generators.

3 patterns built on the F Lyd / A voicing family:

  A. iv_lyd_on_vi_dwell.mid  — Reich Music for 18 Musicians style
                              two-layer time (pulse + breath) dwell on one
                              chord with Lydian #4 "pointing out".
  B. iv_lyd_on_vi_cycle.mid  — Cohn hexatonic cycle traversal of the IV Lyd
                              On VI voicing with Tymoczko-style voice
                              leading minimization.
  C. iv_lyd_on_vi_eno.mid    — Eno Music for Airports style incommensurate
                              loops (lengths 8/13/17/19/23 eighth notes).

Pure stdlib; writes SMF type 0 bytes directly. Output goes to ../output/.
Design rationale lives in ../DESIGN_NOTES.md and ../RESEARCH_NOTES.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

TICKS_PER_BEAT = 480
BPM = 80

# C major key: F Lyd / A means
#   bass A2 (45), slash F3 (53), inner A3-C4-E4-G4 (57,60,64,67), sky B4 (71)
# We expose this as a transposable voicing.


@dataclass(frozen=True)
class IVLydOnVI:
    """IV Lyd On VI voicing template.

    `tonic` is the major-key tonic in semitones from C (e.g. C=0, F=5, G=7).
    The voicing places:
      bass    = VI of key  = tonic + 9  (A in C, D in F, ...)
      slash   = IV of key  = tonic + 5  (F in C)
      inner   = F major 7 = IV, VI, I, III  (F-A-C-E in C)
      sky     = #4 of IV (Lydian)        = tonic + 11 - 12 = tonic + 11
                Equivalently: M7 of VI bass... actually it's the Lydian #4
                of IV which is the chromatic VII of the major key (B in C).
    """

    tonic: int  # 0..11, semitones from C, major key

    def bass(self) -> int:
        return 33 + ((self.tonic + 9) % 12)  # A2 family

    def slash_low(self) -> int:
        return 41 + ((self.tonic + 5) % 12)  # F3 family

    def inner(self) -> list[int]:
        # F-A-C-E in C: 53,57,60,64 → raise to ~A3..G4 range
        f = self.tonic + 5
        a = self.tonic + 9
        c = self.tonic + 12
        e = self.tonic + 16
        g = self.tonic + 19  # G4 ≒ M7 of F
        # anchor to register: lowest in [55..71] approximately
        notes = [a + 48, c + 48, e + 48, g + 48]
        return notes

    def sky(self) -> int:
        # Lydian #4 of IV = VII of key (B in C). Up in B4 register.
        return 59 + ((self.tonic + 11) % 12)


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
    vel = max(1, min(127, vel))
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
    track_data += vlq(0) + meta_track_name(name)
    track_data += vlq(0) + meta_tempo(BPM)
    track_data += vlq(0) + meta_time_sig()

    def sort_key(ev: tuple[int, bytes]) -> tuple[int, int]:
        # NoteOff (0x80) before NoteOn (0x90) at same tick
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
# Helpers — envelopes
# ----------------------------------------------------------------------------


def ramp(t: float, t_start: float, t_full: float, v_off: int, v_on: int) -> int:
    """Linear ramp from v_off at t_start to v_on at t_full. Held outside."""
    if t <= t_start:
        return v_off
    if t >= t_full:
        return v_on
    a = (t - t_start) / (t_full - t_start)
    return int(round(v_off + (v_on - v_off) * a))


def sustained(events: list, ch: int, note: int, start_tick: int, end_tick: int, vel: int) -> None:
    events.append((start_tick, note_on(ch, note, vel)))
    events.append((max(start_tick + 1, end_tick - 5), note_off(ch, note)))


# ----------------------------------------------------------------------------
# Pattern A: Music for 18 Musicians style dwell on F Lyd / A
# ----------------------------------------------------------------------------


def gen_dwell() -> list[tuple[int, bytes]]:
    """80 bars dwell on F Lyd / A. Two-layer time: long breath + 8th pulse.

    Process envelope (each segment is gradual):
      bar  0–8 : bass A2 + low F3 emerge (breath only)
      bar  8–24: inner pulse fades in (A3-C4-E4-G4 broken arp)
      bar 24–40: sky B4 (Lydian #4) "points out" — velocity 0 → full
      bar 40–56: full saturation
      bar 56–64: sky B4 fades
      bar 64–72: inner pulse fades
      bar 72–80: bass + low F decay
    """
    voicing = IVLydOnVI(tonic=0)  # C major key → F Lyd / A
    BAR = 4 * TICKS_PER_BEAT
    EIGHTH = TICKS_PER_BEAT // 2
    total_bars = 80
    total_ticks = total_bars * BAR

    events: list[tuple[int, bytes]] = []

    # --- Breath layer: bass A2 (re-articulated every 8 bars) ---
    bass = voicing.bass()
    for bar in range(0, total_bars, 8):
        start = bar * BAR
        end = min((bar + 8) * BAR, total_ticks)
        # bass velocity envelope: fade in 0-8, sustain 8-72, fade 72-80
        bar_center = bar + 4
        if bar_center < 8:
            vel = ramp(bar_center, 0, 8, 30, 70)
        elif bar_center < 72:
            vel = 70
        else:
            vel = ramp(bar_center, 72, 80, 70, 25)
        sustained(events, 0, bass, start, end, vel)

    # --- Breath layer: low F3 (defining slash tone), re-articulated every 4 bars ---
    low_f = voicing.slash_low()
    for bar in range(0, total_bars, 4):
        start = bar * BAR
        end = min((bar + 4) * BAR, total_ticks)
        bar_center = bar + 2
        if bar_center < 8:
            vel = ramp(bar_center, 0, 8, 25, 65)
        elif bar_center < 72:
            vel = 65
        else:
            vel = ramp(bar_center, 72, 80, 65, 20)
        sustained(events, 0, low_f, start, end, vel)

    # --- Pulse layer: 8th note broken arp A3-C4-E4-G4 ---
    # Pattern: A3 E4 C4 G4 A3 E4 C4 G4 (8 8ths per bar)
    a3, c4, e4, g4 = voicing.inner()
    pulse_pattern = [a3, e4, c4, g4, a3, e4, c4, g4]

    for bar in range(total_bars):
        bar_center = bar + 0.5
        if bar_center < 8:
            vel_base = 0
        elif bar_center < 24:
            vel_base = ramp(bar_center, 8, 24, 0, 60)
        elif bar_center < 64:
            vel_base = 60
        elif bar_center < 72:
            vel_base = ramp(bar_center, 64, 72, 60, 0)
        else:
            vel_base = 0

        if vel_base <= 0:
            continue

        for i, n in enumerate(pulse_pattern):
            t = bar * BAR + i * EIGHTH
            # Slight accent on beats 1 & 3 for natural lilt
            vel = vel_base + (8 if i % 4 == 0 else 0)
            note_dur = EIGHTH - 20
            events.append((t, note_on(0, n, vel)))
            events.append((t + note_dur, note_off(0, n)))

    # --- Sky layer: B4 Lydian #4 "pointing out" ---
    sky = voicing.sky()
    # Re-articulate B4 on bar 1 of each 4-bar group, sustaining 4 bars.
    # Velocity envelope: 0 in bars 0-24, ramp to full in 24-40, hold, decay 56-64.
    for bar in range(0, total_bars, 4):
        bar_center = bar + 2
        if bar_center < 24:
            vel = 0
        elif bar_center < 40:
            vel = ramp(bar_center, 24, 40, 0, 75)
        elif bar_center < 56:
            vel = 75
        elif bar_center < 64:
            vel = ramp(bar_center, 56, 64, 75, 0)
        else:
            vel = 0
        if vel <= 5:
            continue
        start = bar * BAR
        end = min((bar + 4) * BAR, total_ticks)
        sustained(events, 0, sky, start, end, vel)

    return events


# ----------------------------------------------------------------------------
# Pattern B: Cohn hexatonic cycle with Tymoczko voice-leading minimization
# ----------------------------------------------------------------------------


def vl_distance(v1: list[int], v2: list[int]) -> int:
    """L1 voice-leading distance: sum of semitone displacements in best pairing.

    For equal-cardinality chords with sorted pitches and minimal-displacement
    pairing (here we pair by sorted index, which is L1-optimal under bijective
    voice leading per Tymoczko).
    """
    s1 = sorted(v1)
    s2 = sorted(v2)
    return sum(abs(a - b) for a, b in zip(s1, s2))


def best_octave_match(target: list[int], reference: list[int]) -> list[int]:
    """For each note in target, transpose by ±12 to minimize distance to reference."""
    out: list[int] = []
    s_ref = sorted(reference)
    s_tgt = sorted(target)
    for t, r in zip(s_tgt, s_ref):
        candidates = [t - 12, t, t + 12, t + 24, t - 24]
        best = min(candidates, key=lambda x: abs(x - r))
        out.append(best)
    return out


def gen_cycle() -> list[tuple[int, bytes]]:
    """Hexatonic cycle of IV Lyd On VI voicings, voice-leading minimized.

    Path (M3-related tonics): C → A♭ → E → C  (hexatonic cycle, 3 steps)
    Each tonic gets 16 bars dwell. Total = 48 bars + 8 bar coda = 56 bars.
    """
    BAR = 4 * TICKS_PER_BEAT
    EIGHTH = TICKS_PER_BEAT // 2
    dwell_bars = 16
    cycle_tonics = [0, 8, 4, 0]  # C, A♭, E, C (M3 down each step)
    n_segments = len(cycle_tonics)
    total_bars = dwell_bars * n_segments

    events: list[tuple[int, bytes]] = []

    # Build the actual voicings used, with voice-leading minimization between adjacent.
    base_voicing = IVLydOnVI(tonic=cycle_tonics[0])
    base_notes = [base_voicing.bass(), base_voicing.slash_low(),
                  *base_voicing.inner(), base_voicing.sky()]
    voicings_used: list[list[int]] = [base_notes]

    for t in cycle_tonics[1:]:
        v = IVLydOnVI(tonic=t)
        raw = [v.bass(), v.slash_low(), *v.inner(), v.sky()]
        adjusted = best_octave_match(raw, voicings_used[-1])
        voicings_used.append(adjusted)

    # Print VL distances for the log
    for i in range(1, len(voicings_used)):
        d = vl_distance(voicings_used[i - 1], voicings_used[i])
        print(f"    VL distance segment {i - 1}->{i}: {d} semitones")

    # Lay out each segment
    for seg_idx, notes in enumerate(voicings_used):
        seg_start = seg_idx * dwell_bars * BAR
        seg_end = (seg_idx + 1) * dwell_bars * BAR
        # Sustain all notes for the segment, with crossfade-style velocity at boundaries.
        for n_idx, n in enumerate(notes):
            # First 2 bars fade-in, last 2 bars fade-out
            # Layer ramps over 2-bar windows give a smooth crossfade with the next chord
            fade_in_end = seg_start + 2 * BAR
            fade_out_start = seg_end - 2 * BAR
            target_vel = 60 + (10 if n_idx in (6,) else 0)  # boost sky slightly
            # bass and low_f a bit louder
            if n_idx in (0, 1):
                target_vel = 70
            # Articulate each bar to keep MIDI synths from cutting sustain
            for bar_off in range(dwell_bars):
                bar_start = seg_start + bar_off * BAR
                bar_end = bar_start + BAR
                bar_center = bar_start + BAR // 2
                if bar_center < fade_in_end:
                    a = (bar_center - seg_start) / (2 * BAR)
                    vel = int(round(target_vel * a))
                elif bar_center > fade_out_start:
                    a = (seg_end - bar_center) / (2 * BAR)
                    vel = int(round(target_vel * a))
                else:
                    vel = target_vel
                if vel < 5:
                    continue
                sustained(events, 0, n, bar_start, bar_end, vel)

    return events


# ----------------------------------------------------------------------------
# Pattern C: Eno incommensurate loops
# ----------------------------------------------------------------------------


def gen_eno() -> list[tuple[int, bytes]]:
    """Five layers at lengths 8, 13, 17, 19, 23 eighth notes.

    LCM(8,13,17,19,23) = 967,304 eighth notes → effectively non-repeating
    within any realistic listening window. We run for 128 bars (1024 eighths).
    """
    voicing = IVLydOnVI(tonic=0)
    BAR = 4 * TICKS_PER_BEAT
    EIGHTH = TICKS_PER_BEAT // 2
    total_bars = 128
    total_eighths = total_bars * 8

    events: list[tuple[int, bytes]] = []

    # Layer 1: bass A2, length 8 eighths (= 1 bar), re-articulated each bar
    # but with subtle micro-variation: every 5th repetition gets quieter.
    bass = voicing.bass()
    for e_idx in range(0, total_eighths, 8):
        t = e_idx * EIGHTH
        # Bass dur = 8 eighths minus tiny gap
        dur = 8 * EIGHTH - 30
        vel = 60 if (e_idx // 8) % 5 != 0 else 50
        events.append((t, note_on(0, bass, vel)))
        events.append((t + dur, note_off(0, bass)))

    # Layer 2: low F3, length 13 eighths
    low_f = voicing.slash_low()
    for e_idx in range(0, total_eighths, 13):
        t = e_idx * EIGHTH
        dur = 13 * EIGHTH - 30
        events.append((t, note_on(0, low_f, 55)))
        events.append((min(t + dur, total_eighths * EIGHTH), note_off(0, low_f)))

    # Layer 3: inner pulse cycle, length 8 eighths
    a3, c4, e4, g4 = voicing.inner()
    inner_pat = [a3, e4, c4, g4, a3, e4, c4, g4]
    for e_idx in range(total_eighths):
        n = inner_pat[e_idx % 8]
        t = e_idx * EIGHTH
        dur = EIGHTH - 25
        vel = 45 + ((e_idx * 7) % 11) - 5  # slight humanization
        events.append((t, note_on(0, n, vel)))
        events.append((t + dur, note_off(0, n)))

    # Layer 4: inner echo on E4/G4 alternating, length 19 eighths
    echo_pat = [e4 + 12, g4]  # higher echo
    for e_idx in range(0, total_eighths, 19):
        n = echo_pat[(e_idx // 19) % 2]
        t = e_idx * EIGHTH
        dur = 4 * EIGHTH
        events.append((t, note_on(0, n, 45)))
        events.append((min(t + dur, total_eighths * EIGHTH), note_off(0, n)))

    # Layer 5: sky B4 Lydian #4, length 23 eighths, sparse
    sky = voicing.sky()
    for e_idx in range(0, total_eighths, 23):
        t = e_idx * EIGHTH
        dur = 8 * EIGHTH
        # Sky velocity rises gradually from 0 to ~70 over the piece
        prog = e_idx / total_eighths
        vel = int(round(20 + prog * 55))
        events.append((t, note_on(0, sky, vel)))
        events.append((min(t + dur, total_eighths * EIGHTH), note_off(0, sky)))

    # Layer 6 (bonus): occasional sky echo B4+octave at length 17 eighths
    # to add subtle high shimmer in the latter half
    for e_idx in range(int(total_eighths * 0.5), total_eighths, 17):
        t = e_idx * EIGHTH
        dur = 2 * EIGHTH
        events.append((t, note_on(0, sky + 12, 35)))
        events.append((min(t + dur, total_eighths * EIGHTH), note_off(0, sky + 12)))

    return events


# ----------------------------------------------------------------------------
# Pattern D: Arc — 2-minute integrated piece, all 8 math models combined
# ----------------------------------------------------------------------------


def gen_arc() -> list[tuple[int, bytes]]:
    """40 bars @ BPM 80 = 2:00 exactly. Integrates 8 mathematical models:

      1. Cohn hexatonic cycle (PLR walk by M3): C → A♭ → E → C
      2. Tymoczko VL geodesic (L1-minimized per transition)
      3. Reich *Music for 18 Musicians* two-layer time (pulse + breath)
      4. Lydian #4 "pointing out" (sky velocity ramp)
      5. Eno incommensurate cycles (bass/low_F/sky re-attack periods coprime)
      6. Russell LCC outgoingness (Lydian → Lydian #5 inflection at peak)
      7. Stockhausen formula self-similarity (4-bar cell ↔ 40-bar macro)
      8. Reich palindrome (post-peak mirrors pre-peak: ABCDCBA-compressed)

    Macro arc (Stockhausen formula projection of 4-bar attack/develop/peak/release
    onto the 40-bar form):
       bars  0– 8  起 (intro):   F Lyd / A. bass + low F emerging.
       bars  8–16  承1:           + inner pulse fades in, C key dwell.
       bars 16–24  承2/転1:       hexatonic step → A♭ key (D♭ Lyd / F).
       bars 24–32  転2 peak:      hexatonic step → E key (A Lyd / C#),
                                  Lydian #5 chromatic inflection,
                                  sky pointing-out at full velocity.
       bars 32–40  結 (palindrome): return to C key, decay mirroring intro.

    Within each 4-bar micro cell, intensity follows attack(beat1)→develop→
    peak(beat3)→release(beat4) — self-similar to macro form.
    """
    BAR = 4 * TICKS_PER_BEAT
    EIGHTH = TICKS_PER_BEAT // 2
    SIXTEENTH = TICKS_PER_BEAT // 4
    total_bars = 40
    total_ticks = total_bars * BAR

    events: list[tuple[int, bytes]] = []

    # ---- Macro tonic schedule (which key is active in each bar) ----
    # bars 0-16 = C(0), bars 16-24 = A♭(8), bars 24-32 = E(4), bars 32-40 = C(0)
    tonic_schedule: list[int] = []
    for b in range(total_bars):
        if b < 16:
            tonic_schedule.append(0)   # C → F Lyd / A
        elif b < 24:
            tonic_schedule.append(8)   # A♭ → D♭ Lyd / F
        elif b < 32:
            tonic_schedule.append(4)   # E → A Lyd / C#
        else:
            tonic_schedule.append(0)   # back to C

    # ---- Pre-compute voicings with VL minimization at each tonic change ----
    voicings_at: dict[int, dict[str, int]] = {}
    prev_set: list[int] | None = None
    for tonic in [0, 8, 4, 0]:
        v = IVLydOnVI(tonic=tonic)
        raw = {
            "bass": v.bass(),
            "low_f": v.slash_low(),
            "a3": v.inner()[0],
            "c4": v.inner()[1],
            "e4": v.inner()[2],
            "g4": v.inner()[3],
            "sky": v.sky(),
        }
        if prev_set is None:
            voicings_at[tonic] = raw
        else:
            # Apply best_octave_match to each note relative to previous
            ordered = ["bass", "low_f", "a3", "c4", "e4", "g4", "sky"]
            adjusted: dict[str, int] = {}
            for name in ordered:
                candidates = [raw[name] - 12, raw[name], raw[name] + 12]
                ref = prev_set[ordered.index(name)] if prev_set else raw[name]
                adjusted[name] = min(candidates, key=lambda x: abs(x - ref))
            voicings_at[tonic] = adjusted
        prev_set = [voicings_at[tonic][k] for k in ["bass", "low_f", "a3", "c4", "e4", "g4", "sky"]]

    # For the return to C at bar 32, we want the same voicing as bar 0
    # (palindrome). Force it explicitly.
    voicings_at[0] = {
        "bass": IVLydOnVI(0).bass(),
        "low_f": IVLydOnVI(0).slash_low(),
        "a3": IVLydOnVI(0).inner()[0],
        "c4": IVLydOnVI(0).inner()[1],
        "e4": IVLydOnVI(0).inner()[2],
        "g4": IVLydOnVI(0).inner()[3],
        "sky": IVLydOnVI(0).sky(),
    }

    def current_voicing(bar: int) -> dict[str, int]:
        return voicings_at[tonic_schedule[bar]]

    # ---- Macro envelopes for each layer (palindromic around bar 20) ----

    def bass_vel(bar: int) -> int:
        # Always present. Fade in 0-4, full 4-36, fade 36-40.
        if bar < 4:
            return ramp(bar, 0, 4, 25, 72)
        elif bar < 36:
            return 72
        else:
            return ramp(bar, 36, 40, 72, 22)

    def low_f_vel(bar: int) -> int:
        if bar < 4:
            return ramp(bar, 0, 4, 20, 65)
        elif bar < 36:
            return 65
        else:
            return ramp(bar, 36, 40, 65, 18)

    def pulse_vel(bar: int) -> int:
        # In bars 8-32, palindrome decay 32-36
        if bar < 8:
            return 0
        elif bar < 12:
            return ramp(bar, 8, 12, 0, 55)
        elif bar < 32:
            return 55
        elif bar < 36:
            return ramp(bar, 32, 36, 55, 0)
        else:
            return 0

    def sky_vel(bar: int) -> int:
        # Pointing out: starts bar 12 sparse, full at bar 24 (peak), decay 32-36
        if bar < 12:
            return 0
        elif bar < 20:
            return ramp(bar, 12, 20, 0, 60)
        elif bar < 28:
            # Peak zone (centered bar 24)
            return ramp(bar, 20, 24, 60, 85) if bar < 24 else ramp(bar, 24, 28, 85, 65)
        elif bar < 32:
            return 65
        elif bar < 36:
            return ramp(bar, 32, 36, 65, 0)
        else:
            return 0

    # ---- Eno incommensurate re-attack offsets ----
    # bass: re-articulate every 4 bars (period = 4 bars = 32 eighths)
    # low_f: re-articulate every 3 bars (period = 24 eighths)  ← coprime with 4 within the 12-bar lcm
    # sky: re-articulate every 5 bars (period = 40 eighths) ← coprime with 4 and 3

    # ---- Bass layer ----
    for bar in range(0, total_bars, 4):
        v = current_voicing(bar)
        start = bar * BAR
        end = min((bar + 4) * BAR, total_ticks)
        vel = bass_vel(bar + 2)
        if vel >= 5:
            sustained(events, 0, v["bass"], start, end, vel)

    # ---- Low F (slash defining tone) layer ----
    # Re-articulate every 3 bars (Eno incommensurate)
    bar = 0
    while bar < total_bars:
        v = current_voicing(bar)
        start = bar * BAR
        end = min((bar + 3) * BAR, total_ticks)
        vel = low_f_vel(bar + 1)
        if vel >= 5:
            sustained(events, 0, v["low_f"], start, end, vel)
        bar += 3

    # ---- Inner pulse layer: 8th note broken arp A3-E4-C4-G4 ----
    # Pattern within each bar: A3 E4 C4 G4 A3 E4 C4 G4 (8 8ths)
    # Stockhausen formula: within each 4-bar cell, micro arc on velocity
    for bar in range(total_bars):
        base_vel = pulse_vel(bar)
        if base_vel <= 0:
            continue
        v = current_voicing(bar)
        pat = [v["a3"], v["e4"], v["c4"], v["g4"], v["a3"], v["e4"], v["c4"], v["g4"]]
        # Stockhausen formula micro envelope: 4-bar cell shape (attack/develop/peak/release)
        cell_pos = bar % 4
        # subtle bar-level emphasis: bar 0 of cell is loudest, bar 3 softest
        cell_modifier = [+6, +2, +4, -2][cell_pos]
        for i, n in enumerate(pat):
            t = bar * BAR + i * EIGHTH
            # 8th note accent on beats 1 and 3 (i=0, i=4)
            beat_accent = 6 if i in (0, 4) else 0
            vel = max(20, min(110, base_vel + cell_modifier + beat_accent))
            note_dur = EIGHTH - 25
            events.append((t, note_on(0, n, vel)))
            events.append((t + note_dur, note_off(0, n)))

    # ---- Sky note ("pointing out" the Lydian #4) ----
    # Re-articulate every 5 bars (Eno incommensurate with bass/low_F)
    bar = 0
    while bar < total_bars:
        v = current_voicing(bar)
        sky_note = v["sky"]
        # Russell LCC outgoingness: at the peak (bars 24-26 in E key segment),
        # raise sky by 1 semitone for one bar = Lydian → Lydian #5 inflection.
        if bar == 25:
            # 1-bar duration at +1 semitone, then back
            start = bar * BAR
            end = (bar + 1) * BAR
            vel = sky_vel(bar)
            if vel >= 5:
                sustained(events, 0, sky_note + 1, start, end, vel)
            # Continue main sky from bar 26
            bar = 26
            continue
        start = bar * BAR
        end = min((bar + 5) * BAR, total_ticks)
        vel = sky_vel(bar + 2)
        if vel >= 5:
            sustained(events, 0, sky_note, start, end, vel)
        bar += 5

    # ---- Sparkle layer: high sky echo (sky + 12) ----
    # Sparse, only in peak zone (bars 22-30), every 2 bars
    for bar in range(22, 30, 2):
        v = current_voicing(bar)
        echo_note = v["sky"] + 12
        start = bar * BAR + EIGHTH * 2  # offset onto beat 1.5 for shimmer
        dur = EIGHTH * 3
        vel = max(0, sky_vel(bar) - 25)
        if vel >= 5:
            events.append((start, note_on(0, echo_note, vel)))
            events.append((start + dur, note_off(0, echo_note)))

    return events


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def main() -> None:
    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    patterns = [
        ("iv_lyd_on_vi_arc.mid", "IV Lyd On VI — Arc (8 models integrated, 2:00)", gen_arc()),
        ("iv_lyd_on_vi_dwell.mid", "IV Lyd On VI — Dwell (Reich Mf18 style)", gen_dwell()),
        ("iv_lyd_on_vi_cycle.mid", "IV Lyd On VI — Hexatonic Cycle (Cohn/Tymoczko)", gen_cycle()),
        ("iv_lyd_on_vi_eno.mid", "IV Lyd On VI — Incommensurate Loops (Eno)", gen_eno()),
    ]

    print(f"BPM={BPM}, ticks/beat={TICKS_PER_BEAT}")
    print(f"Output: {out_dir}/")
    for filename, name, events in patterns:
        path = out_dir / filename
        write_smf(path, events, name)
        notes = sum(1 for _, e in events if (e[0] & 0xF0) == 0x90)
        last_tick = max((t for t, _ in events), default=0)
        bars = last_tick / (4 * TICKS_PER_BEAT)
        dur_sec = last_tick / TICKS_PER_BEAT * 60 / BPM
        print(f"  {filename}: {notes} notes, {bars:.1f} bars, {dur_sec:.1f}s")


if __name__ == "__main__":
    main()
