//! Geomonic — Phase 1 minimal MIDI generator (I–V–vi–IV, quarter-note, close voicing)

use nih_plug::prelude::*;
use std::sync::Arc;

// ============================================================================
// Parameters
// ============================================================================

#[derive(Params)]
pub struct GeomonicParams {
    /// Root pitch class (0=C, 1=C#, ..., 11=B)
    #[id = "root"]
    pub root: IntParam,

    /// Output octave for the bass note of the chord (default = octave 4 → C4 = MIDI 60)
    #[id = "octave"]
    pub octave: IntParam,

    /// Velocity for emitted notes
    #[id = "velocity"]
    pub velocity: IntParam,
}

impl Default for GeomonicParams {
    fn default() -> Self {
        const NOTE_NAMES: [&str; 12] = [
            "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
        ];
        Self {
            root: IntParam::new("Root", 0, IntRange::Linear { min: 0, max: 11 })
                .with_value_to_string(Arc::new(|v| NOTE_NAMES[v as usize % 12].to_string())),
            octave: IntParam::new("Octave", 4, IntRange::Linear { min: 1, max: 7 }),
            velocity: IntParam::new("Velocity", 96, IntRange::Linear { min: 1, max: 127 }),
        }
    }
}

// ============================================================================
// Music theory (Phase 1: hard-coded I–V–vi–IV in major key)
// ============================================================================

/// Diatonic chord triads relative to a major key root.
/// Each entry: (root offset in semitones from key root, quality: 0=major, 1=minor)
const PROGRESSION_I_V_VI_IV: [(i32, u8); 4] = [
    (0, 0),  // I  (major)
    (7, 0),  // V  (major)
    (9, 1),  // vi (minor)
    (5, 0),  // IV (major)
];

/// Generate a close-voicing triad given a bass MIDI note and quality.
/// Returns [root, third, fifth] MIDI notes.
fn close_triad(bass_midi: i32, quality: u8) -> [u8; 3] {
    let third = if quality == 0 { 4 } else { 3 }; // major=4, minor=3 semitones
    let fifth = 7;
    [
        bass_midi.clamp(0, 127) as u8,
        (bass_midi + third).clamp(0, 127) as u8,
        (bass_midi + fifth).clamp(0, 127) as u8,
    ]
}

// ============================================================================
// Plugin
// ============================================================================

pub struct GeomonicPlugin {
    params: Arc<GeomonicParams>,

    /// Sample rate in Hz
    sample_rate: f32,

    /// Current step index in the progression (0..4)
    step: usize,

    /// Notes currently held by the generator (so we can NoteOff them)
    held_notes: Vec<u8>,

    /// Beat position at which the current step started (in quarter notes)
    /// None = nothing playing yet / waiting for first trigger
    step_started_at: Option<f64>,

    /// Last DAW playing state, for resetting on play
    was_playing: bool,
}

impl Default for GeomonicPlugin {
    fn default() -> Self {
        Self {
            params: Arc::new(GeomonicParams::default()),
            sample_rate: 44100.0,
            step: 0,
            held_notes: Vec::new(),
            step_started_at: None,
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

    // Instrument layout: no audio input, silent stereo output, MIDI in/out
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

    fn reset(&mut self) {
        self.step = 0;
        self.held_notes.clear();
        self.step_started_at = None;
        self.was_playing = false;
    }

    fn process(
        &mut self,
        buffer: &mut Buffer,
        _aux: &mut AuxiliaryBuffers,
        context: &mut impl ProcessContext<Self>,
    ) -> ProcessStatus {
        // Silence the audio output buffer (this is a MIDI generator)
        for ch in buffer.as_slice() {
            for s in ch.iter_mut() {
                *s = 0.0;
            }
        }

        // Snapshot transport state before any context.send_event() calls
        // (transport borrows context immutably; send_event needs mutable)
        let (playing, block_start_beats_opt, bpm) = {
            let transport = context.transport();
            (
                transport.playing,
                transport.pos_beats(),
                transport.tempo.unwrap_or(120.0),
            )
        };

        // On stop: release any held notes
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
            self.step_started_at = None;
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

        // If nothing scheduled yet, schedule the next trigger at the next integer beat
        // ≥ block_start_beats.
        let next_trigger_beat = self
            .step_started_at
            .map(|t| t + 1.0) // every quarter note
            .unwrap_or_else(|| block_start_beats.ceil().max(block_start_beats));

        if next_trigger_beat < block_end_beats {
            // Compute sample offset of the trigger within this block
            let offset_beats = (next_trigger_beat - block_start_beats).max(0.0);
            let offset_samples =
                (offset_beats * (60.0 / bpm) * self.sample_rate as f64) as u32;
            let timing = offset_samples.min(buffer.samples() as u32 - 1);

            // NoteOff previous chord
            for n in self.held_notes.drain(..) {
                context.send_event(NoteEvent::NoteOff {
                    timing,
                    voice_id: None,
                    channel: 0,
                    note: n,
                    velocity: 0.0,
                });
            }

            // Compute new chord
            let key_root = self.params.root.value() as i32;
            let octave = self.params.octave.value();
            let velocity_u8 = self.params.velocity.value() as u8;
            let (degree_offset, quality) = PROGRESSION_I_V_VI_IV[self.step];

            // Bass MIDI note = (octave * 12) + (key_root + degree_offset) mod 12, with octave wrap kept inside the requested octave
            let bass_pc = ((key_root + degree_offset) % 12 + 12) % 12;
            let bass_midi = octave * 12 + bass_pc;
            let triad = close_triad(bass_midi, quality);

            let vel_f = velocity_u8 as f32 / 127.0;
            for &n in &triad {
                context.send_event(NoteEvent::NoteOn {
                    timing,
                    voice_id: None,
                    channel: 0,
                    note: n,
                    velocity: vel_f,
                });
                self.held_notes.push(n);
            }

            self.step_started_at = Some(next_trigger_beat);
            self.step = (self.step + 1) % PROGRESSION_I_V_VI_IV.len();
        }

        ProcessStatus::Normal
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
