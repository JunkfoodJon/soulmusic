"""
SoulMusic — acoustic/probe.py
Shell acoustic properties and operational presets.

Each preset encodes recommended emitter parameters for targeting a drone
through a specific shell material.  Parameters tuned for MEMS gyroscope
resonance disruption in the 18–35 kHz band.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

import numpy as np

SAMPLE_RATE = 96000
SPEED_OF_SOUND = 343.0


# ─────────────────────────────────────────────────────────────────────────────
#  Shell Profile (physical material model)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ShellProfile:
    """Acoustic material properties of a drone protective shell."""

    name: str
    acoustic_impedance_mrayl: float     # Z = ρ·c  (MRayl = 10⁶ Pa·s/m)
    attenuation_db_per_cm: float        # one-way attenuation at ~25 kHz
    resonant_thickness_mm: float        # quarter-wavelength resonance thickness
    transmission_coefficient: float     # pressure transmission fraction  (0–1)
    notes: str = ""


# Physical shell profiles for common drone body materials
SHELL_PROFILES: Dict[str, ShellProfile] = {
    "none": ShellProfile(
        name="none",
        acoustic_impedance_mrayl=0.000,
        attenuation_db_per_cm=0.00,
        resonant_thickness_mm=0.0,
        transmission_coefficient=1.00,
        notes="Open air — no enclosure.",
    ),
    "foam": ShellProfile(
        name="foam",
        acoustic_impedance_mrayl=0.030,
        attenuation_db_per_cm=0.80,
        resonant_thickness_mm=6.8,
        transmission_coefficient=0.88,
        notes="EVA/EPP foam: low acoustic impedance, good coupling.",
    ),
    "plastic": ShellProfile(
        name="plastic",
        acoustic_impedance_mrayl=2.40,
        attenuation_db_per_cm=1.20,
        resonant_thickness_mm=2.9,
        transmission_coefficient=0.72,
        notes="ABS/polycarbonate: moderate impedance mismatch.",
    ),
    "composite": ShellProfile(
        name="composite",
        acoustic_impedance_mrayl=6.50,
        attenuation_db_per_cm=2.10,
        resonant_thickness_mm=1.5,
        transmission_coefficient=0.55,
        notes="CFRP/fibreglass: anisotropic; structural coupling via shock bursts.",
    ),
    "metal": ShellProfile(
        name="metal",
        acoustic_impedance_mrayl=17.00,
        attenuation_db_per_cm=0.60,
        resonant_thickness_mm=0.8,
        transmission_coefficient=0.35,
        notes="Aluminium/titanium: high Z mismatch; rely on chassis resonance.",
    ),
    "unknown": ShellProfile(
        name="unknown",
        acoustic_impedance_mrayl=2.40,
        attenuation_db_per_cm=1.20,
        resonant_thickness_mm=2.9,
        transmission_coefficient=0.65,
        notes="Unknown material — adaptive sweep as fallback.",
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
#  Shell Presets (operational emitter settings)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Each value is a plain dict so soul_gui.py can access keys directly
#  (e.g. preset["mode"], preset["power"]).
#
#  Keys:
#    mode        — "sweep" | "burst" | "shock"
#    power       — normalised output amplitude  0.0–1.0
#    pulse_ms    — burst/shock pulse duration in milliseconds (0 = N/A)
#    rep_rate_hz — burst/shock repetition rate in Hz (0 = N/A)
#    description — human-readable summary

SHELL_PRESETS: Dict[str, Dict[str, Any]] = {
    "none": {
        "mode":        "sweep",
        "power":       0.30,
        "pulse_ms":    0,
        "rep_rate_hz": 0,
        "description": "Open-air direct coupling.  Continuous sweep sufficient.",
    },
    "foam": {
        "mode":        "burst",
        "power":       0.60,
        "pulse_ms":    5.0,
        "rep_rate_hz": 20,
        "description": "Light foam absorbs little energy.  Short bursts at resonant frequency.",
    },
    "plastic": {
        "mode":        "burst",
        "power":       0.80,
        "pulse_ms":    3.0,
        "rep_rate_hz": 50,
        "description": "Thin plastic couples well at shell resonance.  Moderate burst rep rate.",
    },
    "composite": {
        "mode":        "shock",
        "power":       1.00,
        "pulse_ms":    1.0,
        "rep_rate_hz": 100,
        "description": "CFRP/fibreglass — shock burst propagates via structural vibration through the shell.",
    },
    "metal": {
        "mode":        "shock",
        "power":       1.00,
        "pulse_ms":    0.5,
        "rep_rate_hz": 200,
        "description": "Metal chassis — maximum power, narrow shock pulses exploit mechanical resonance.",
    },
    "unknown": {
        "mode":        "sweep",
        "power":       0.70,
        "pulse_ms":    2.0,
        "rep_rate_hz": 50,
        "description": "Unknown shell — adaptive sweep scans for resonance coupling signature.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  Probe Chirp Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_probe_chirp(
    f_start: float = 18_000.0,
    f_end: float = 35_000.0,
    duration_ms: float = 5.0,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Generate a linear chirp probe signal for shell classification.

    Returns a float32 ndarray normalised to [-1, 1].
    """
    n_samples = int(sample_rate * duration_ms / 1000.0)
    t = np.arange(n_samples, dtype=np.float64) / sample_rate
    dur = n_samples / sample_rate
    phase = 2.0 * np.pi * (f_start * t + (f_end - f_start) * t * t / (2.0 * dur))
    chirp = np.sin(phase).astype(np.float32)
    return chirp


# ─────────────────────────────────────────────────────────────────────────────
#  Reflection Analysis
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ReflectionProfile:
    """Result of analysing a probe chirp reflection."""
    shell_class: str
    attenuation_db: float
    correlation_peak: float = 0.0


def analyze_reflection(
    captured: np.ndarray,
    estimated_range_m: float,
    sample_rate: int = SAMPLE_RATE,
) -> Optional[ReflectionProfile]:
    """Classify shell material from a captured probe reflection.

    Correlates the captured audio with the reference probe chirp at the
    expected round-trip delay, measures attenuation, and maps it to the
    closest shell profile.

    Returns a ReflectionProfile with .shell_class and .attenuation_db.
    """
    probe = generate_probe_chirp(sample_rate=sample_rate)
    probe_len = len(probe)

    rt_delay = 2.0 * estimated_range_m / SPEED_OF_SOUND
    delay_samples = int(rt_delay * sample_rate)

    # Extract the region where the echo is expected
    start = max(0, delay_samples - probe_len // 4)
    end = min(len(captured), delay_samples + probe_len + probe_len // 4)
    if end - start < probe_len:
        return ReflectionProfile(shell_class="unknown", attenuation_db=0.0)

    region = captured[start:end].astype(np.float64)

    # Cross-correlate with probe to find echo
    corr = np.correlate(region, probe.astype(np.float64), mode='valid')
    if len(corr) == 0:
        return ReflectionProfile(shell_class="unknown", attenuation_db=0.0)

    peak_corr = float(np.max(np.abs(corr)))
    ref_energy = float(np.sum(probe.astype(np.float64) ** 2))
    if ref_energy < 1e-12:
        return ReflectionProfile(shell_class="unknown", attenuation_db=0.0)

    # Normalised correlation → effective transmission coefficient
    norm_corr = peak_corr / ref_energy
    # Clamp to [0, 1]
    norm_corr = min(max(norm_corr, 0.0), 1.0)

    # Attenuation in dB (relative to perfect echo)
    if norm_corr > 1e-6:
        attenuation_db = float(-20.0 * np.log10(norm_corr))
    else:
        attenuation_db = 60.0  # treat as near-total loss

    # Classify by matching attenuation to shell profiles
    best_class = "unknown"
    best_dist = float('inf')
    for name, profile in SHELL_PROFILES.items():
        if name == "unknown":
            continue
        # Expected round-trip attenuation for this material
        expected_atten = profile.attenuation_db_per_cm * 0.2  # thin shell ~2mm
        # Distance metric: how close is measured attenuation to profile's expected
        t_coeff = profile.transmission_coefficient
        expected_total_db = -20.0 * np.log10(max(t_coeff, 1e-6))
        dist = abs(attenuation_db - expected_total_db)
        if dist < best_dist:
            best_dist = dist
            best_class = name

    return ReflectionProfile(
        shell_class=best_class,
        attenuation_db=attenuation_db,
        correlation_peak=peak_corr,
    )
