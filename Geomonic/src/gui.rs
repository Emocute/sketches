//! Geomonic GUI — 4-axis selector + status panel + geometric preview
//!
//! The preview area visualizes the active transform:
//!   - Tonnetz: triangular lattice with current chord highlighted
//!   - Symmetry 3/4/6: regular polygon on a 12-tone clock
//!   - Spectral: vertical harmonic series with selected partials
//!   - PCSet: pitch-class clock with the current set highlighted
//!   - None / Orbifold: pitch-class clock with current chord

use crate::{progression_steps, GeomonicParams, ProgressionId, TransformId, NOTE_NAMES};
use nih_plug::prelude::*;
use nih_plug_egui::egui::{self, Color32, FontId, Pos2, Rect, Sense, Stroke, Vec2};
use nih_plug_egui::widgets::ParamSlider;
use nih_plug_egui::{create_egui_editor, EguiState};
use parking_lot::Mutex;
use std::sync::Arc;

/// Shared state from the audio thread (for displaying current step / chord)
#[derive(Default)]
pub struct GuiState {
    pub current_step: usize,
    pub current_chord_root_pc: i32,
    pub current_chord_quality_name: String,
}

pub fn editor_state() -> Arc<EguiState> {
    EguiState::from_size(560, 720)
}

pub fn create_editor(
    state: Arc<EguiState>,
    params: Arc<GeomonicParams>,
    gui_state: Arc<Mutex<GuiState>>,
) -> Option<Box<dyn Editor>> {
    create_egui_editor(
        state,
        (),
        |_egui_ctx, _state| {},
        move |egui_ctx, setter, _state| {
            egui::CentralPanel::default().show(egui_ctx, |ui| {
                ui.spacing_mut().slider_width = 220.0;

                ui.vertical_centered(|ui| {
                    ui.heading(egui::RichText::new("GEOMONIC").color(Color32::from_rgb(220, 220, 240)));
                    ui.label(
                        egui::RichText::new("Progression × Transform × Rhythm × Voicing")
                            .color(Color32::from_gray(140))
                            .small(),
                    );
                });

                ui.add_space(8.0);
                ui.separator();
                ui.add_space(4.0);

                // 4 axes
                ui.group(|ui| {
                    ui.label(egui::RichText::new("AXES").color(Color32::from_rgb(180, 200, 220)).strong());
                    ui.add_space(2.0);

                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new("A. Progression").monospace());
                        ui.add(ParamSlider::for_param(&params.progression, setter));
                    });
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new("B. Transform  ").monospace());
                        ui.add(ParamSlider::for_param(&params.transform, setter));
                    });
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new("C. Rhythm     ").monospace());
                        ui.add(ParamSlider::for_param(&params.rhythm, setter));
                    });
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new("D. Voicing    ").monospace());
                        ui.add(ParamSlider::for_param(&params.voicing, setter));
                    });
                });

                ui.add_space(6.0);

                // Common params
                ui.group(|ui| {
                    ui.label(egui::RichText::new("KEY & DYNAMICS").color(Color32::from_rgb(180, 200, 220)).strong());
                    ui.add_space(2.0);

                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new("Root          ").monospace());
                        ui.add(ParamSlider::for_param(&params.root, setter));
                    });
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new("Octave        ").monospace());
                        ui.add(ParamSlider::for_param(&params.octave, setter));
                    });
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new("Velocity      ").monospace());
                        ui.add(ParamSlider::for_param(&params.velocity, setter));
                    });
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new("Swing         ").monospace());
                        ui.add(ParamSlider::for_param(&params.swing, setter));
                    });
                });

                ui.add_space(8.0);

                // Status / preview
                let gs = gui_state.lock();
                let step = gs.current_step;
                let chord_root = gs.current_chord_root_pc;
                let chord_quality = gs.current_chord_quality_name.clone();
                drop(gs);

                ui.group(|ui| {
                    ui.label(egui::RichText::new("STATUS").color(Color32::from_rgb(180, 200, 220)).strong());
                    let chord_name = if (0..12).contains(&chord_root) && !chord_quality.is_empty() {
                        format!("{}{}", NOTE_NAMES[chord_root as usize], chord_quality)
                    } else {
                        "—".to_string()
                    };
                    ui.label(egui::RichText::new(format!("Step:  {}", step + 1)).monospace());
                    ui.label(egui::RichText::new(format!("Chord: {}", chord_name)).monospace());
                });

                ui.add_space(8.0);

                // Geometric preview
                ui.group(|ui| {
                    ui.label(egui::RichText::new("GEOMETRY").color(Color32::from_rgb(180, 200, 220)).strong());
                    let key_root = params.root.value() as i32;
                    let transform = params.transform.value();
                    let progression = params.progression.value();
                    draw_geometry(ui, transform, progression, key_root, step);
                });
            });
        },
    )
}

fn draw_geometry(
    ui: &mut egui::Ui,
    transform: TransformId,
    progression: ProgressionId,
    key_root: i32,
    step: usize,
) {
    let desired_size = Vec2::new(ui.available_width(), 260.0);
    let (response, painter) = ui.allocate_painter(desired_size, Sense::hover());
    let rect = response.rect;
    let center = rect.center();
    let radius = rect.height().min(rect.width()) * 0.40;

    // Background
    painter.rect_filled(rect, 4.0, Color32::from_gray(18));

    // Pick the active pitch classes for the current chord
    let chords = if transform.overrides_progression() {
        transform.override_steps()
    } else {
        progression_steps(progression)
    };
    let active_pcs: Vec<i32> = if chords.is_empty() {
        Vec::new()
    } else {
        let chord = chords[step % chords.len()];
        let root_pc = ((key_root + chord.degree) % 12 + 12) % 12;
        chord
            .quality
            .intervals()
            .iter()
            .map(|&iv| (root_pc + iv) % 12)
            .collect()
    };

    match transform {
        TransformId::Sym3 | TransformId::Sym4 | TransformId::Sym6 => {
            draw_polygon_clock(&painter, center, radius, transform, &active_pcs);
        }
        TransformId::Spectral => {
            draw_spectral(&painter, rect, key_root);
        }
        TransformId::Tonnetz => {
            draw_tonnetz(&painter, rect, &active_pcs);
        }
        _ => {
            draw_pc_clock(&painter, center, radius, &active_pcs);
        }
    }
}

fn draw_pc_clock(painter: &egui::Painter, center: Pos2, radius: f32, active_pcs: &[i32]) {
    // 12 points on a circle, labelled with note names
    for pc in 0..12 {
        let angle = -std::f32::consts::FRAC_PI_2 + (pc as f32) * std::f32::consts::TAU / 12.0;
        let p = center + Vec2::new(angle.cos(), angle.sin()) * radius;
        let is_active = active_pcs.contains(&(pc as i32));
        let color = if is_active {
            Color32::from_rgb(255, 220, 120)
        } else {
            Color32::from_gray(80)
        };
        let r = if is_active { 9.0 } else { 5.0 };
        painter.circle_filled(p, r, color);
        painter.text(
            p + Vec2::new(0.0, 18.0),
            egui::Align2::CENTER_CENTER,
            NOTE_NAMES[pc],
            FontId::monospace(11.0),
            Color32::from_gray(180),
        );
    }
    // Connect active PCs
    if active_pcs.len() >= 2 {
        for i in 0..active_pcs.len() {
            for j in (i + 1)..active_pcs.len() {
                let a = active_pcs[i];
                let b = active_pcs[j];
                let angle_a = -std::f32::consts::FRAC_PI_2 + (a as f32) * std::f32::consts::TAU / 12.0;
                let angle_b = -std::f32::consts::FRAC_PI_2 + (b as f32) * std::f32::consts::TAU / 12.0;
                let pa = center + Vec2::new(angle_a.cos(), angle_a.sin()) * radius;
                let pb = center + Vec2::new(angle_b.cos(), angle_b.sin()) * radius;
                painter.line_segment([pa, pb], Stroke::new(1.2, Color32::from_rgba_unmultiplied(255, 200, 100, 100)));
            }
        }
    }
}

fn draw_polygon_clock(
    painter: &egui::Painter,
    center: Pos2,
    radius: f32,
    transform: TransformId,
    active_pcs: &[i32],
) {
    // Same 12-tone clock backdrop
    draw_pc_clock(painter, center, radius, active_pcs);

    // Overlay the symmetric polygon vertices in a contrasting color
    let n = match transform {
        TransformId::Sym3 => 3,
        TransformId::Sym4 => 4,
        TransformId::Sym6 => 6,
        _ => 0,
    };
    if n == 0 {
        return;
    }
    let step = 12 / n;
    let mut verts: Vec<Pos2> = Vec::new();
    for i in 0..n {
        let pc = i * step;
        let angle = -std::f32::consts::FRAC_PI_2 + (pc as f32) * std::f32::consts::TAU / 12.0;
        let p = center + Vec2::new(angle.cos(), angle.sin()) * radius;
        verts.push(p);
    }
    // Close the polygon
    for i in 0..verts.len() {
        let a = verts[i];
        let b = verts[(i + 1) % verts.len()];
        painter.line_segment([a, b], Stroke::new(2.0, Color32::from_rgb(140, 200, 255)));
    }
}

fn draw_spectral(painter: &egui::Painter, rect: Rect, key_root: i32) {
    // Vertical harmonic series — 16 partials, the selected partials highlighted
    let n_partials = 16;
    let x_left = rect.left() + 30.0;
    let x_right = rect.right() - 30.0;
    let y_top = rect.top() + 20.0;
    let y_bot = rect.bottom() - 20.0;

    // baseline
    painter.line_segment(
        [Pos2::new(x_left, y_bot), Pos2::new(x_right, y_bot)],
        Stroke::new(1.0, Color32::from_gray(80)),
    );

    let highlight = [1, 3, 5, 7, 9, 11, 13]; // odd harmonics (Spectral signature)
    for k in 1..=n_partials {
        let t = (k as f32 - 1.0) / (n_partials as f32 - 1.0);
        let x = x_left + (x_right - x_left) * t;
        let h = (y_bot - y_top) * (1.0 / (k as f32).sqrt());
        let y_top_bar = y_bot - h;
        let color = if highlight.contains(&k) {
            Color32::from_rgb(255, 200, 100)
        } else {
            Color32::from_gray(70)
        };
        painter.line_segment([Pos2::new(x, y_bot), Pos2::new(x, y_top_bar)], Stroke::new(3.0, color));
        if k <= 8 {
            painter.text(
                Pos2::new(x, y_bot + 12.0),
                egui::Align2::CENTER_CENTER,
                format!("{}", k),
                FontId::monospace(10.0),
                Color32::from_gray(140),
            );
        }
    }

    painter.text(
        Pos2::new(rect.left() + 10.0, rect.top() + 10.0),
        egui::Align2::LEFT_TOP,
        format!("Root: {}", NOTE_NAMES[((key_root % 12 + 12) % 12) as usize]),
        FontId::monospace(11.0),
        Color32::from_gray(180),
    );
}

fn draw_tonnetz(painter: &egui::Painter, rect: Rect, active_pcs: &[i32]) {
    // Triangular lattice: x axis = perfect fifth (+7), y axis = major third (+4)
    let cell_w = 56.0;
    let cell_h = 48.0;
    let cols = (rect.width() / cell_w).ceil() as i32 + 1;
    let rows = (rect.height() / cell_h).ceil() as i32 + 1;
    let origin = rect.left_top() + Vec2::new(cell_w * 0.5, cell_h * 0.5);

    for row in 0..rows {
        for col in 0..cols {
            let x_off = if row % 2 == 0 { 0.0 } else { cell_w * 0.5 };
            let x = origin.x + (col as f32) * cell_w + x_off;
            let y = origin.y + (row as f32) * cell_h;
            if x < rect.left() || x > rect.right() || y < rect.top() || y > rect.bottom() {
                continue;
            }
            // PC at this node = col * 7 + row * 4 (mod 12)
            let pc = ((col * 7 + row * 4) % 12 + 12) % 12;
            let is_active = active_pcs.contains(&pc);
            let color = if is_active {
                Color32::from_rgb(255, 220, 120)
            } else {
                Color32::from_gray(60)
            };
            painter.circle_filled(Pos2::new(x, y), if is_active { 8.0 } else { 4.0 }, color);
            painter.text(
                Pos2::new(x, y + 14.0),
                egui::Align2::CENTER_CENTER,
                NOTE_NAMES[pc as usize],
                FontId::monospace(9.0),
                Color32::from_gray(150),
            );
        }
    }
}

/// Helper used from the plugin to populate human-readable chord-quality strings.
pub fn quality_short_name(quality: crate::ChordQuality) -> &'static str {
    use crate::ChordQuality::*;
    match quality {
        Major => "",
        Minor => "m",
        Dim => "°",
        Aug => "+",
        Dom7 => "7",
        Maj7 => "M7",
        Min7 => "m7",
        HalfDim7 => "ø7",
        Dim7 => "°7",
        MinMaj7 => "mM7",
        Sus4 => "sus4",
    }
}
