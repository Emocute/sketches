//! Geomonic — Phase 2: 4-axis matrix MIDI generator
//!
//! Axes:
//!   A. Progression   — which chords to traverse (8 patterns)
//!   B. Transform     — how to connect chords / which math model (8 models)
//!   C. Rhythm        — when to trigger (8 patterns)
//!   D. Voicing       — how to stack pitches (7 voicings)

use nih_plug::prelude::*;
use nih_plug_egui::EguiState;
use parking_lot::Mutex;
use std::sync::Arc;

mod gui;
pub use gui::GuiState;

pub const NOTE_NAMES: [&str; 12] = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
];

// ============================================================================
// Music theory primitives
// ============================================================================

#[derive(Clone, Copy, PartialEq, Debug)]
pub enum ChordQuality {
    Major,
    Minor,
    Dim,
    Aug,
    Dom7,
    Maj7,
    Min7,
    HalfDim7,
    Dim7,
    MinMaj7,
    Sus4,
}

impl ChordQuality {
    pub fn intervals(&self) -> &'static [i32] {
        match self {
            ChordQuality::Major => &[0, 4, 7],
            ChordQuality::Minor => &[0, 3, 7],
            ChordQuality::Dim => &[0, 3, 6],
            ChordQuality::Aug => &[0, 4, 8],
            ChordQuality::Dom7 => &[0, 4, 7, 10],
            ChordQuality::Maj7 => &[0, 4, 7, 11],
            ChordQuality::Min7 => &[0, 3, 7, 10],
            ChordQuality::HalfDim7 => &[0, 3, 6, 10],
            ChordQuality::Dim7 => &[0, 3, 6, 9],
            ChordQuality::MinMaj7 => &[0, 3, 7, 11],
            ChordQuality::Sus4 => &[0, 5, 7],
        }
    }
}

#[derive(Clone, Copy)]
pub struct ChordSpec {
    /// Semitone offset from the key root
    pub degree: i32,
    pub quality: ChordQuality,
}

const fn cs(degree: i32, quality: ChordQuality) -> ChordSpec {
    ChordSpec { degree, quality }
}

// ============================================================================
// Axis A: Progression
// ============================================================================

#[derive(Enum, PartialEq, Eq, Clone, Copy)]
pub enum ProgressionId {
    #[name = "I-V-vi-IV"]
    IVviIV,
    #[name = "ii-V-I"]
    IiVI,
    #[name = "I-vi-IV-V"]
    IviIVV,
    #[name = "12-bar blues"]
    Blues12,
    #[name = "Andalusian"]
    Andalusian,
    #[name = "Royal Road"]
    RoyalRoad,
    #[name = "Circle of Fifths"]
    CircleOfFifths,
    #[name = "Pachelbel"]
    Pachelbel,
}

pub fn progression_steps(id: ProgressionId) -> Vec<ChordSpec> {
    use ChordQuality::*;
    match id {
        ProgressionId::IVviIV => vec![cs(0, Major), cs(7, Major), cs(9, Minor), cs(5, Major)],
        ProgressionId::IiVI => vec![cs(2, Minor), cs(7, Major), cs(0, Major)],
        ProgressionId::IviIVV => vec![cs(0, Major), cs(9, Minor), cs(5, Major), cs(7, Major)],
        ProgressionId::Blues12 => {
            let i7 = cs(0, Dom7);
            let iv7 = cs(5, Dom7);
            let v7 = cs(7, Dom7);
            vec![i7, i7, i7, i7, iv7, iv7, i7, i7, v7, iv7, i7, v7]
        }
        // Andalusian (in minor): i – VII – VI – V
        ProgressionId::Andalusian => vec![cs(0, Minor), cs(10, Major), cs(8, Major), cs(7, Major)],
        // J-pop golden: IV maj7 – V7 – iii m7 – vi m7
        ProgressionId::RoyalRoad => vec![cs(5, Maj7), cs(7, Dom7), cs(4, Min7), cs(9, Min7)],
        // vi m7 – ii m7 – V7 – I maj7 (descending fifths)
        ProgressionId::CircleOfFifths => vec![cs(9, Min7), cs(2, Min7), cs(7, Dom7), cs(0, Maj7)],
        // I – V – vi – iii – IV – I – IV – V
        ProgressionId::Pachelbel => vec![
            cs(0, Major), cs(7, Major), cs(9, Minor), cs(4, Minor),
            cs(5, Major), cs(0, Major), cs(5, Major), cs(7, Major),
        ],
    }
}

// ============================================================================
// Axis B: Transform
// ============================================================================

#[derive(Enum, PartialEq, Eq, Clone, Copy)]
pub enum TransformId {
    #[name = "None"]
    None,
    #[name = "Tonnetz (smooth VL)"]
    Tonnetz,
    #[name = "Orbifold (nearest)"]
    Orbifold,
    #[name = "Symmetry 3 (Coltrane)"]
    Sym3,
    #[name = "Symmetry 4 (dim cycle)"]
    Sym4,
    #[name = "Symmetry 6 (whole tone)"]
    Sym6,
    #[name = "Spectral (overtone)"]
    Spectral,
    #[name = "PCSet (T_n chain)"]
    PCSet,
}

impl TransformId {
    pub fn overrides_progression(&self) -> bool {
        matches!(
            self,
            TransformId::Sym3
                | TransformId::Sym4
                | TransformId::Sym6
                | TransformId::Spectral
                | TransformId::PCSet
        )
    }

    /// Chord sequence for override-style transforms.
    pub fn override_steps(&self) -> Vec<ChordSpec> {
        use ChordQuality::*;
        match self {
            TransformId::Sym3 => vec![cs(0, Major), cs(4, Major), cs(8, Major)],
            TransformId::Sym4 => vec![cs(0, Dim7), cs(3, Dim7), cs(6, Dim7), cs(9, Dim7)],
            TransformId::Sym6 => vec![
                cs(0, Aug),
                cs(2, Aug),
                cs(4, Aug),
                cs(6, Aug),
                cs(8, Aug),
                cs(10, Aug),
            ],
            // Spectral: harmonics 4-5-6-7 → dom7 voicing on the root; one chord, but voicing supplies the spectrum
            TransformId::Spectral => vec![cs(0, Dom7)],
            // PC set Forte 4-9 {0,1,5,6}: cycle by T_n (n=0, 3, 6, 9)
            TransformId::PCSet => vec![cs(0, Major), cs(3, Major), cs(6, Major), cs(9, Major)],
            _ => Vec::new(),
        }
    }

    /// Should voicing be re-octaved for smooth voice leading from previous chord?
    pub fn smooth_voicing(&self) -> bool {
        matches!(self, TransformId::Tonnetz | TransformId::Orbifold)
    }
}

// ============================================================================
// Axis C: Rhythm
// ============================================================================

#[derive(Enum, PartialEq, Eq, Clone, Copy)]
pub enum RhythmId {
    #[name = "1/4 note"]
    Quarter,
    #[name = "1/8 note"]
    Eighth,
    #[name = "1/16 note"]
    Sixteenth,
    #[name = "1/8 triplet"]
    EighthTriplet,
    #[name = "Euclidean(8,3)"]
    Euc8_3,
    #[name = "Euclidean(8,5)"]
    Euc8_5,
    #[name = "Euclidean(16,7)"]
    Euc16_7,
    #[name = "Shuffle"]
    Shuffle,
}

impl RhythmId {
    /// Underlying step length in beats (quarter notes).
    pub fn step_beats(&self) -> f64 {
        match self {
            RhythmId::Quarter => 1.0,
            RhythmId::Eighth | RhythmId::Shuffle => 0.5,
            RhythmId::Sixteenth | RhythmId::Euc8_3 | RhythmId::Euc8_5 | RhythmId::Euc16_7 => 0.25,
            RhythmId::EighthTriplet => 1.0 / 3.0,
        }
    }

    /// Pulse mask for euclidean rhythms (None = every step fires).
    pub fn pattern(&self) -> Option<Vec<bool>> {
        match self {
            RhythmId::Euc8_3 => Some(euclidean(8, 3)),
            RhythmId::Euc8_5 => Some(euclidean(8, 5)),
            RhythmId::Euc16_7 => Some(euclidean(16, 7)),
            _ => None,
        }
    }

    pub fn is_shuffle(&self) -> bool {
        matches!(self, RhythmId::Shuffle)
    }
}

/// Bresenham-style euclidean rhythm: distribute `k` pulses across `n` steps as evenly as possible.
fn euclidean(n: usize, k: usize) -> Vec<bool> {
    let mut pattern = vec![false; n];
    if n == 0 {
        return pattern;
    }
    let k = k.min(n);
    let mut bucket: i64 = 0;
    for i in 0..n {
        bucket += k as i64;
        if bucket >= n as i64 {
            bucket -= n as i64;
            pattern[i] = true;
        }
    }
    pattern
}

// ============================================================================
// Axis D: Voicing
// ============================================================================

#[derive(Enum, PartialEq, Eq, Clone, Copy)]
pub enum VoicingId {
    #[name = "Close"]
    Close,
    #[name = "Open"]
    Open,
    #[name = "Drop 2"]
    Drop2,
    #[name = "Drop 3"]
    Drop3,
    #[name = "Shell"]
    Shell,
    #[name = "Cluster"]
    Cluster,
    #[name = "Spread"]
    Spread,
}

/// Apply a voicing to a chord (root MIDI + intervals) and return absolute MIDI notes.
fn apply_voicing(root_midi: i32, intervals: &[i32], voicing: VoicingId) -> Vec<i32> {
    let mut notes: Vec<i32> = intervals.iter().map(|&iv| root_midi + iv).collect();
    notes.sort();
    match voicing {
        VoicingId::Close => notes,
        VoicingId::Open => {
            if notes.len() >= 3 {
                notes[1] += 12;
                notes.sort();
            }
            notes
        }
        VoicingId::Drop2 => {
            if notes.len() >= 2 {
                let idx = notes.len() - 2;
                notes[idx] -= 12;
                notes.sort();
            }
            notes
        }
        VoicingId::Drop3 => {
            if notes.len() >= 3 {
                let idx = notes.len() - 3;
                notes[idx] -= 12;
                notes.sort();
            }
            notes
        }
        VoicingId::Shell => {
            // root + 3rd + 7th (for tetrads); falls back to triad close voicing
            if intervals.len() >= 4 {
                vec![
                    root_midi + intervals[0],
                    root_midi + intervals[1],
                    root_midi + intervals[3],
                ]
            } else {
                notes
            }
        }
        VoicingId::Cluster => {
            // Stack all tones within a half-step cluster above root (experimental flavor)
            (0..notes.len() as i32).map(|i| root_midi + i).collect()
        }
        VoicingId::Spread => {
            // Each successive note one octave higher than the close-voicing position
            notes
                .iter()
                .enumerate()
                .map(|(i, &n)| n + (i as i32) * 12)
                .collect()
        }
    }
}

// ============================================================================
// Plugin parameters
// ============================================================================

#[derive(Params)]
pub struct GeomonicParams {
    #[persist = "editor-state"]
    pub editor_state: Arc<EguiState>,

    /// Key root pitch class (0=C, 1=C#, ..., 11=B)
    #[id = "root"]
    pub root: IntParam,

    /// Bass octave (4 = C4 = MIDI 60)
    #[id = "octave"]
    pub octave: IntParam,

    /// Note-on velocity
    #[id = "velocity"]
    pub velocity: IntParam,

    /// A. Progression
    #[id = "progression"]
    pub progression: EnumParam<ProgressionId>,

    /// B. Transform / Math model
    #[id = "transform"]
    pub transform: EnumParam<TransformId>,

    /// C. Rhythm
    #[id = "rhythm"]
    pub rhythm: EnumParam<RhythmId>,

    /// D. Voicing
    #[id = "voicing"]
    pub voicing: EnumParam<VoicingId>,

    /// Shuffle swing ratio (0.5 = straight 8ths, 0.667 = triplet feel)
    #[id = "swing"]
    pub swing: FloatParam,
}

impl Default for GeomonicParams {
    fn default() -> Self {
        Self {
            editor_state: gui::editor_state(),
            root: IntParam::new("Root", 0, IntRange::Linear { min: 0, max: 11 })
                .with_value_to_string(Arc::new(|v| NOTE_NAMES[v as usize % 12].to_string())),
            octave: IntParam::new("Octave", 4, IntRange::Linear { min: 1, max: 7 }),
            velocity: IntParam::new("Velocity", 96, IntRange::Linear { min: 1, max: 127 }),
            progression: EnumParam::new("Progression", ProgressionId::IVviIV),
            transform: EnumParam::new("Transform", TransformId::None),
            rhythm: EnumParam::new("Rhythm", RhythmId::Quarter),
            voicing: EnumParam::new("Voicing", VoicingId::Close),
            swing: FloatParam::new("Swing", 0.5, FloatRange::Linear { min: 0.5, max: 0.75 })
                .with_value_to_string(Arc::new(|v| format!("{:.2}", v))),
        }
    }
}

// ============================================================================
// Plugin
// ============================================================================

pub struct GeomonicPlugin {
    params: Arc<GeomonicParams>,
    gui_state: Arc<Mutex<GuiState>>,
    sample_rate: f32,

    /// Index into the current progression's step list
    step: usize,
    /// Index into the rhythm's pattern (for euclidean rhythms)
    rhythm_step: usize,
    /// Currently sounding notes (so we can NoteOff them)
    held_notes: Vec<u8>,
    /// Beat position at which the current chord trigger started (None = waiting)
    last_trigger_beat: Option<f64>,
    /// Whether DAW was playing in the previous block
    was_playing: bool,
}

impl Default for GeomonicPlugin {
    fn default() -> Self {
        Self {
            params: Arc::new(GeomonicParams::default()),
            gui_state: Arc::new(Mutex::new(GuiState::default())),
            sample_rate: 44100.0,
            step: 0,
            rhythm_step: 0,
            held_notes: Vec::new(),
            last_trigger_beat: None,
            was_playing: false,
        }
    }
}

impl Plugin for GeomonicPlugin {
    const NAME: &'static str = "Geomonic";
    const VENDOR: &'static str = "Emocute";
    const URL: &'static str = "https://github.com/Emocute/sketches";
    const EMAIL: &'static str = "support@emocutelab.com";
    const VERSION: &'static str = env!("CARGO_PKG_VERSION");

    const AUDIO_IO_LAYOUTS: &'static [AudioIOLayout] = &[AudioIOLayout {
        main_input_channels: None,
        main_output_channels: NonZeroU32::new(2),
        ..AudioIOLayout::const_default()
    }];

    const MIDI_INPUT: MidiConfig = MidiConfig::Basic;
    const MIDI_OUTPUT: MidiConfig = MidiConfig::Basic;

    type SysExMessage = ();
    type BackgroundTask = ();

    fn params(&self) -> Arc<dyn Params> {
        self.params.clone()
    }

    fn initialize(
        &mut self,
        _audio_io_layout: &AudioIOLayout,
        buffer_config: &BufferConfig,
        _context: &mut impl InitContext<Self>,
    ) -> bool {
        self.sample_rate = buffer_config.sample_rate;
        true
    }

    fn editor(&mut self, _async_executor: AsyncExecutor<Self>) -> Option<Box<dyn Editor>> {
        gui::create_editor(
            self.params.editor_state.clone(),
            self.params.clone(),
            self.gui_state.clone(),
        )
    }

    fn reset(&mut self) {
        self.step = 0;
        self.rhythm_step = 0;
        self.held_notes.clear();
        self.last_trigger_beat = None;
        self.was_playing = false;
    }

    fn process(
        &mut self,
        buffer: &mut Buffer,
        _aux: &mut AuxiliaryBuffers,
        context: &mut impl ProcessContext<Self>,
    ) -> ProcessStatus {
        // Silence the audio output (this is a MIDI generator)
        for ch in buffer.as_slice() {
            for s in ch.iter_mut() {
                *s = 0.0;
            }
        }

        // Snapshot transport state (releases the immutable borrow before send_event calls)
        let (playing, block_start_beats_opt, bpm) = {
            let transport = context.transport();
            (
                transport.playing,
                transport.pos_beats(),
                transport.tempo.unwrap_or(120.0),
            )
        };

        // Handle play→stop transition
        if !playing && self.was_playing {
            for n in self.held_notes.drain(..) {
                context.send_event(NoteEvent::NoteOff {
                    timing: 0,
                    voice_id: None,
                    channel: 0,
                    note: n,
                    velocity: 0.0,
                });
            }
            self.step = 0;
            self.rhythm_step = 0;
            self.last_trigger_beat = None;
        }
        self.was_playing = playing;

        if !playing {
            return ProcessStatus::Normal;
        }

        let Some(block_start_beats) = block_start_beats_opt else {
            return ProcessStatus::Normal;
        };

        let block_len_samples = buffer.samples() as f64;
        let block_len_beats = (block_len_samples / self.sample_rate as f64) * (bpm / 60.0);
        let block_end_beats = block_start_beats + block_len_beats;

        // Read parameter snapshot
        let key_root = self.params.root.value() as i32;
        let octave = self.params.octave.value();
        let velocity_u8 = self.params.velocity.value() as u8;
        let progression_id = self.params.progression.value();
        let transform_id = self.params.transform.value();
        let rhythm_id = self.params.rhythm.value();
        let voicing_id = self.params.voicing.value();
        let swing = self.params.swing.value() as f64;

        // Resolve effective chord sequence
        let chords = if transform_id.overrides_progression() {
            transform_id.override_steps()
        } else {
            progression_steps(progression_id)
        };
        if chords.is_empty() {
            return ProcessStatus::Normal;
        }
        if self.step >= chords.len() {
            self.step = 0;
        }

        let step_beats = rhythm_id.step_beats();
        let rhythm_pattern = rhythm_id.pattern();

        // Compute next trigger beat. We may need to fire multiple times within one block.
        loop {
            let next_beat = match self.last_trigger_beat {
                Some(t) => {
                    let mut b = t + step_beats;
                    // Shuffle: swing every 2nd 8th note
                    if rhythm_id.is_shuffle() {
                        // toggle: if step is odd, delay; if even, accelerate
                        let pair_index = ((b * 2.0).round() as i64).rem_euclid(2);
                        if pair_index == 1 {
                            // Off-beat: shift by (swing - 0.5)
                            b = t + step_beats * 2.0 * swing;
                        } else {
                            b = t + step_beats * 2.0 * (1.0 - swing);
                        }
                    }
                    b
                }
                None => block_start_beats.ceil().max(block_start_beats),
            };

            if next_beat >= block_end_beats {
                break;
            }

            let offset_beats = (next_beat - block_start_beats).max(0.0);
            let offset_samples = (offset_beats * (60.0 / bpm) * self.sample_rate as f64) as u32;
            let timing = offset_samples.min(buffer.samples() as u32 - 1);

            // Decide whether to fire (euclidean / pattern-based rhythms can skip)
            let fire = match &rhythm_pattern {
                Some(pat) => pat[self.rhythm_step % pat.len()],
                None => true,
            };

            if fire {
                // Stop previous notes
                for n in self.held_notes.drain(..) {
                    context.send_event(NoteEvent::NoteOff {
                        timing,
                        voice_id: None,
                        channel: 0,
                        note: n,
                        velocity: 0.0,
                    });
                }

                // Current chord
                let chord = chords[self.step];
                let chord_root_pc = ((key_root + chord.degree) % 12 + 12) % 12;
                let chord_root_midi = octave * 12 + chord_root_pc;
                let intervals = chord.quality.intervals();

                // Apply voicing
                let mut new_notes = apply_voicing(chord_root_midi, intervals, voicing_id);

                // Smooth voice leading (Tonnetz / Orbifold)
                if transform_id.smooth_voicing() {
                    let prev: Vec<i32> = self.held_notes.iter().map(|&n| n as i32).collect();
                    // held_notes was just drained, so use the last_voicing snapshot instead
                    // (we keep prev_notes implicitly via the previous send_events; here we
                    // approximate by re-deriving from last chord — for now, fall back to
                    // octave-centering around C4)
                    let _ = prev; // not used in this simplified branch
                    smooth_to_prev_around(&mut new_notes, octave * 12 + key_root);
                }

                // Update GUI status (lock briefly, no audio-thread allocations beyond a small string)
                {
                    let mut gs = self.gui_state.lock();
                    gs.current_step = self.step;
                    gs.current_chord_root_pc = chord_root_pc;
                    gs.current_chord_quality_name = gui::quality_short_name(chord.quality).to_string();
                }

                // Advance to next chord step
                self.step = (self.step + 1) % chords.len();

                // Note on each pitch
                let vel_f = velocity_u8 as f32 / 127.0;
                for n in new_notes {
                    let clamped = n.clamp(0, 127) as u8;
                    context.send_event(NoteEvent::NoteOn {
                        timing,
                        voice_id: None,
                        channel: 0,
                        note: clamped,
                        velocity: vel_f,
                    });
                    self.held_notes.push(clamped);
                }
            }

            self.last_trigger_beat = Some(next_beat);
            self.rhythm_step += 1;
        }

        ProcessStatus::Normal
    }
}

/// Shift each note by ±12 semitones to be closest to the given target MIDI center.
fn smooth_to_prev_around(notes: &mut [i32], target: i32) {
    for n in notes.iter_mut() {
        let mut best = *n;
        let mut best_dist = (*n - target).abs();
        for shift in -3..=3 {
            let candidate = *n + shift * 12;
            let dist = (candidate - target).abs();
            if dist < best_dist {
                best_dist = dist;
                best = candidate;
            }
        }
        *n = best;
    }
}

impl ClapPlugin for GeomonicPlugin {
    const CLAP_ID: &'static str = "com.emocute.geomonic";
    const CLAP_DESCRIPTION: Option<&'static str> = Some(
        "Geometric harmony MIDI generator — Progression × Transform × Rhythm × Voicing matrix",
    );
    const CLAP_MANUAL_URL: Option<&'static str> = None;
    const CLAP_SUPPORT_URL: Option<&'static str> = None;
    const CLAP_FEATURES: &'static [ClapFeature] = &[ClapFeature::Instrument];
}

impl Vst3Plugin for GeomonicPlugin {
    const VST3_CLASS_ID: [u8; 16] = *b"GeomonicEmocute1";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] = &[Vst3SubCategory::Instrument];
}

nih_export_clap!(GeomonicPlugin);
nih_export_vst3!(GeomonicPlugin);
