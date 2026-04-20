"""
SoulMusic — acoustic/probe.py
Shell acoustic properties and operational presets.

Each preset encodes recommended emitter parameters for targeting a drone
through a specific shell material.  Parameters tuned for MEMS gyroscope
resonance disruption in the 18–35 kHz band.
"""

from dataclasses import dataclass
from typing import Dict, Any


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
