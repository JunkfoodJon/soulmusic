#!/usr/bin/env python3
"""
SoulMusic — bench_test.py
Physical bench test script for validating MEMS gyroscope acoustic resonance.

Hardware setup:
  ┌──────────┐  I²S/USB  ┌──────────┐  wire  ┌───────────────┐
  │ PC / Pi  │──────────→│ DAC/Amp  │───────→│  Transducer   │
  │ (this    │           └──────────┘        │  (25kHz piezo) │
  │  script) │                               └───────┬───────┘
  │          │                                   sound│(ultrasonic)
  │          │                               ┌───────▼───────┐
  │          │  USB/serial                   │  MEMS sensor  │
  │          │←──────────────────────────────│  (MPU-6050    │
  │          │  (gyro I²C via Arduino/Pi)    │   on breakout)│
  └──────────┘                               └───────────────┘

Required hardware:
  - Ultrasonic transducer (e.g. Murata MA40S4S, 25/40kHz piezo)
  - Amplifier board driving the transducer (Class-D, I²S or analog input)
  - Audio output interface (USB soundcard with ≥96kHz sample rate, or I²S DAC)
  - MEMS breakout board (MPU-6050, BMI270, etc.)
  - Arduino or second Pi reading gyro data via I²C → serial to this PC

Required Python packages:
  pip install numpy sounddevice pyserial matplotlib

Usage:
  python bench_test.py                   # interactive menu
  python bench_test.py --list-devices    # list audio output devices
  python bench_test.py --sensor MPU-6050 # target a specific sensor
  python bench_test.py --sweep           # broad sweep (unknown sensor)
  python bench_test.py --burst MPU-6050  # impulse burst at known resonance
  python bench_test.py --ladder MPU-6050 # SubharmonicLadder zone walk
  python bench_test.py --dry-run         # generate waveforms + plot, no output
"""

import sys
import os
import argparse
import time
import json
import struct
from pathlib import Path
from datetime import datetime

import numpy as np

# Add SoulMusic dir to path so we can import acoustic modules
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from acoustic.resonance import (
    SweepConfig, BurstConfig,
    generate_chirp, generate_burst_train,
    get_broad_sweep, get_targeted_sweep,
    get_broad_burst, get_targeted_burst, get_shock_burst,
    SubharmonicLadder, MEMS_PROFILES,
)

# ── Optional imports (degrade gracefully) ────────────────────

try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    HAS_PLT = True
except ImportError:
    HAS_PLT = False


# ═══════════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════════

SAMPLE_RATE = 96000        # Must be ≥ 2× highest frequency (Nyquist)
RESULTS_DIR = _SCRIPT_DIR / "bench_results"


# ═══════════════════════════════════════════════════════════════
#  Audio Output
# ═══════════════════════════════════════════════════════════════

def list_audio_devices():
    """Print available audio output devices."""
    if not HAS_SD:
        print("ERROR: sounddevice not installed. Run: pip install sounddevice")
        return
    print("\n── Audio Output Devices ──")
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if d["max_output_channels"] > 0:
            sr = int(d["default_samplerate"])
            print(f"  [{i}] {d['name']}  (out={d['max_output_channels']}ch, sr={sr}Hz)")
    print()


def play_waveform(waveform: np.ndarray, device: int | None = None,
                  sample_rate: int = SAMPLE_RATE):
    """Play a waveform through the audio output device.

    Blocks until playback completes.
    """
    if not HAS_SD:
        print("ERROR: sounddevice not installed.")
        return
    print(f"  Playing {len(waveform)} samples ({len(waveform)/sample_rate:.3f}s) "
          f"@ {sample_rate} Hz ...", end="", flush=True)
    sd.play(waveform, samplerate=sample_rate, device=device, blocking=True)
    print(" done.", flush=True)


# ═══════════════════════════════════════════════════════════════
#  Gyro Serial Reader (Arduino/Pi sending I²C data)
# ═══════════════════════════════════════════════════════════════

# Expected serial protocol from Arduino:
#   Each line: "GX,GY,GZ\n" (gyro X/Y/Z in deg/s as floats)
#   e.g.:  "0.12,-0.05,0.03\n"
#   At ~100 Hz (10ms between readings)

class GyroReader:
    """Reads real-time gyro data from an Arduino/Pi over serial."""

    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.1):
        if not HAS_SERIAL:
            raise RuntimeError("pyserial not installed. Run: pip install pyserial")
        self.ser = serial.Serial(port, baud, timeout=timeout)
        self.ser.reset_input_buffer()
        self.data: list[dict] = []
        self._recording = False

    def start_recording(self):
        """Begin accumulating timestamped gyro readings."""
        self.data = []
        self.ser.reset_input_buffer()
        self._recording = True

    def stop_recording(self) -> list[dict]:
        """Stop recording and return accumulated data."""
        self._recording = False
        return self.data

    def poll(self) -> dict | None:
        """Read one gyro sample. Returns None if no data available."""
        try:
            line = self.ser.readline().decode("ascii", errors="replace").strip()
            if not line:
                return None
            parts = line.split(",")
            if len(parts) < 3:
                return None
            sample = {
                "t": time.monotonic(),
                "gx": float(parts[0]),
                "gy": float(parts[1]),
                "gz": float(parts[2]),
            }
            if self._recording:
                self.data.append(sample)
            return sample
        except (ValueError, OSError):
            return None

    def close(self):
        self.ser.close()


def list_serial_ports():
    """Print available serial ports."""
    if not HAS_SERIAL:
        print("WARNING: pyserial not installed — gyro logging disabled.")
        return
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("  No serial ports found.")
        return
    print("\n── Serial Ports ──")
    for p in ports:
        print(f"  {p.device}  —  {p.description}")
    print()


# ═══════════════════════════════════════════════════════════════
#  Result Logging
# ═══════════════════════════════════════════════════════════════

def save_result(test_name: str, params: dict, gyro_data: list[dict] | None,
                waveform: np.ndarray | None = None):
    """Save a bench test result to disk for later analysis."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = RESULTS_DIR / f"{ts}_{test_name}"

    result = {
        "test": test_name,
        "timestamp": ts,
        "params": params,
        "gyro_samples": len(gyro_data) if gyro_data else 0,
    }

    if gyro_data:
        # Compute magnitude stats
        mags = [np.sqrt(s["gx"]**2 + s["gy"]**2 + s["gz"]**2) for s in gyro_data]
        result["gyro_magnitude_mean"] = float(np.mean(mags))
        result["gyro_magnitude_max"] = float(np.max(mags))
        result["gyro_magnitude_std"] = float(np.std(mags))

        # Save raw gyro data
        gyro_path = f"{base}_gyro.json"
        with open(gyro_path, "w") as f:
            json.dump(gyro_data, f)
        result["gyro_file"] = gyro_path

    if waveform is not None:
        wav_path = f"{base}_waveform.npy"
        np.save(wav_path, waveform)
        result["waveform_file"] = wav_path

    meta_path = f"{base}_meta.json"
    with open(meta_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"  Results saved: {meta_path}", flush=True)
    return result


# ═══════════════════════════════════════════════════════════════
#  Visualization
# ═══════════════════════════════════════════════════════════════

def plot_waveform(waveform: np.ndarray, title: str = "Waveform",
                  sample_rate: int = SAMPLE_RATE):
    """Plot waveform time domain + frequency spectrum."""
    if not HAS_PLT:
        print("  (matplotlib not installed — skipping plot)")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))
    fig.suptitle(title, fontweight="bold")

    # Time domain (show first 10ms for detail)
    show_samples = min(len(waveform), int(sample_rate * 0.01))
    t_ms = np.arange(show_samples) / sample_rate * 1000
    ax1.plot(t_ms, waveform[:show_samples], linewidth=0.5, color="#9145ff")
    ax1.set_xlabel("Time (ms)")
    ax1.set_ylabel("Amplitude")
    ax1.set_title("Time Domain (first 10ms)")
    ax1.grid(True, alpha=0.3)

    # Frequency domain
    n = len(waveform)
    fft = np.abs(np.fft.rfft(waveform)) / n
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
    # Focus on 15–40 kHz (the interesting region)
    mask = (freqs >= 15000) & (freqs <= 40000)
    ax2.plot(freqs[mask] / 1000, 20 * np.log10(fft[mask] + 1e-12),
             linewidth=0.8, color="#9145ff")
    ax2.set_xlabel("Frequency (kHz)")
    ax2.set_ylabel("Magnitude (dB)")
    ax2.set_title("Frequency Spectrum (15–40 kHz)")
    ax2.grid(True, alpha=0.3)

    # Mark known MEMS resonances
    for name, prof in MEMS_PROFILES.items():
        f_khz = prof["resonance_hz"] / 1000
        if 15 <= f_khz <= 40:
            ax2.axvline(f_khz, color="red", alpha=0.3, linestyle="--", linewidth=0.7)
            ax2.text(f_khz, ax2.get_ylim()[1] - 3, name,
                     fontsize=6, ha="center", color="red", alpha=0.6)

    plt.tight_layout()
    plt.show(block=False)
    plt.pause(0.1)


def plot_gyro_data(gyro_data: list[dict], title: str = "Gyro Response",
                   attack_start: float | None = None,
                   attack_end: float | None = None):
    """Plot gyro X/Y/Z and magnitude over time, with attack window marked."""
    if not HAS_PLT or not gyro_data:
        return

    t0 = gyro_data[0]["t"]
    t = [s["t"] - t0 for s in gyro_data]
    gx = [s["gx"] for s in gyro_data]
    gy = [s["gy"] for s in gyro_data]
    gz = [s["gz"] for s in gyro_data]
    mag = [np.sqrt(s["gx"]**2 + s["gy"]**2 + s["gz"]**2) for s in gyro_data]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    fig.suptitle(title, fontweight="bold")

    ax1.plot(t, gx, label="Gyro X", linewidth=0.8, alpha=0.8)
    ax1.plot(t, gy, label="Gyro Y", linewidth=0.8, alpha=0.8)
    ax1.plot(t, gz, label="Gyro Z", linewidth=0.8, alpha=0.8)
    ax1.set_ylabel("Angular rate (deg/s)")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    ax2.plot(t, mag, label="Magnitude", linewidth=0.8, color="#9145ff")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("|ω| (deg/s)")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    if attack_start is not None and attack_end is not None:
        for ax in (ax1, ax2):
            ax.axvspan(attack_start - t0, attack_end - t0,
                       color="red", alpha=0.1, label="Attack window")

    plt.tight_layout()
    plt.show(block=False)
    plt.pause(0.1)


# ═══════════════════════════════════════════════════════════════
#  Test Routines
# ═══════════════════════════════════════════════════════════════

def _collect_gyro(gyro: GyroReader | None, duration_s: float) -> list[dict]:
    """Collect gyro data for a given duration. Returns empty list if no gyro."""
    if gyro is None:
        time.sleep(duration_s)
        return []
    gyro.start_recording()
    end = time.monotonic() + duration_s
    while time.monotonic() < end:
        gyro.poll()
        time.sleep(0.005)  # ~200Hz poll rate
    return gyro.stop_recording()


def test_baseline(gyro: GyroReader | None, duration_s: float = 5.0) -> list[dict]:
    """Record baseline gyro data with NO acoustic emission.

    This establishes the sensor's noise floor — what gyro output
    looks like when nothing is happening.  All subsequent tests
    compare against this baseline.
    """
    print("\n═══ BASELINE (no emission) ═══")
    print(f"  Recording {duration_s}s of gyro data with no acoustic output...")
    data = _collect_gyro(gyro, duration_s)
    if data:
        mags = [np.sqrt(s["gx"]**2 + s["gy"]**2 + s["gz"]**2) for s in data]
        print(f"  Baseline noise: mean={np.mean(mags):.4f} "
              f"max={np.max(mags):.4f} std={np.std(mags):.4f} deg/s")
        save_result("baseline", {"duration_s": duration_s}, data)
        plot_gyro_data(data, "Baseline — No Emission")
    else:
        print("  (no gyro connected — baseline skipped)")
    return data


def test_broadband_sweep(device: int | None = None, gyro: GyroReader | None = None,
                         dry_run: bool = False):
    """Broad chirp sweep across 18–35 kHz.

    Use when the target sensor model is unknown.  Covers all known
    MEMS resonances in a single sweep.
    """
    print("\n═══ TEST: Broadband Sweep (18–35 kHz) ═══")
    waveform = get_broad_sweep(duration_ms=200, amplitude=0.8)
    # Repeat for 3 seconds of continuous sweeping
    reps = int(3.0 / (200 / 1000))
    full = np.tile(waveform, reps)
    params = {"type": "broadband_sweep", "freq_start": 18000, "freq_end": 35000,
              "sweep_ms": 200, "total_s": 3.0}

    plot_waveform(waveform, "Broadband Sweep 18–35 kHz")

    if dry_run:
        print("  (dry run — not playing)")
        save_result("broadband_sweep", params, None, waveform)
        return

    # Record: 2s baseline → 3s attack → 2s recovery
    print("  Phase 1: 2s pre-attack baseline")
    pre = _collect_gyro(gyro, 2.0)

    print("  Phase 2: 3s broadband sweep emission")
    attack_t0 = time.monotonic()
    if gyro:
        gyro.start_recording()
    play_waveform(full, device=device)
    attack_t1 = time.monotonic()
    during = gyro.stop_recording() if gyro else []

    print("  Phase 3: 2s post-attack recovery")
    post = _collect_gyro(gyro, 2.0)

    all_data = pre + during + post
    save_result("broadband_sweep", params, all_data, waveform)
    if all_data:
        plot_gyro_data(all_data, "Broadband Sweep — Gyro Response",
                       attack_t0, attack_t1)


def test_targeted_burst(sensor: str, device: int | None = None,
                        gyro: GyroReader | None = None, dry_run: bool = False):
    """Impulse burst targeted at a specific MEMS sensor's resonance."""
    if sensor not in MEMS_PROFILES:
        print(f"  ERROR: Unknown sensor '{sensor}'")
        print(f"  Known sensors: {', '.join(MEMS_PROFILES.keys())}")
        return

    profile = MEMS_PROFILES[sensor]
    freq = profile["resonance_hz"]
    print(f"\n═══ TEST: Targeted Burst — {sensor} ({freq} Hz) ═══")

    waveform = get_targeted_burst(sensor, rep_rate_hz=50, pulse_ms=3.0,
                                  train_ms=3000)
    params = {"type": "targeted_burst", "sensor": sensor, "freq_hz": freq,
              "rep_rate_hz": 50, "pulse_ms": 3.0, "total_s": 3.0}

    plot_waveform(waveform, f"Targeted Burst — {sensor} ({freq} Hz)")

    if dry_run:
        print("  (dry run — not playing)")
        save_result(f"targeted_burst_{sensor}", params, None, waveform)
        return

    # 2s baseline → 3s attack → 2s recovery
    print("  Phase 1: 2s pre-attack baseline")
    pre = _collect_gyro(gyro, 2.0)

    print(f"  Phase 2: 3s targeted burst @ {freq} Hz ± 1 kHz")
    attack_t0 = time.monotonic()
    if gyro:
        gyro.start_recording()
    play_waveform(waveform, device=device)
    attack_t1 = time.monotonic()
    during = gyro.stop_recording() if gyro else []

    print("  Phase 3: 2s post-attack recovery")
    post = _collect_gyro(gyro, 2.0)

    all_data = pre + during + post
    save_result(f"targeted_burst_{sensor}", params, all_data, waveform)
    if all_data:
        plot_gyro_data(all_data, f"Targeted Burst — {sensor} ({freq} Hz)",
                       attack_t0, attack_t1)


def _emit_and_measure(freq: int, duration_ms: int, device: int | None,
                      gyro: GyroReader | None,
                      settle_ms: int = 500) -> dict:
    """Emit a single-frequency burst and measure gyro response.

    Core measurement primitive for all adaptive scan routines.
    Returns {freq_hz, gyro_mag_mean, gyro_mag_max, gyro_mag_std, samples}.
    """
    cfg = BurstConfig(
        freq_start=freq, freq_end=freq,
        pulse_ms=3.0, rise_ms=0.08, rep_rate_hz=50,
        train_duration_ms=duration_ms, sample_rate=SAMPLE_RATE, amplitude=1.0,
    )
    waveform = generate_burst_train(cfg)

    # settle → emit → settle
    _collect_gyro(gyro, settle_ms / 1000.0)

    if gyro:
        gyro.start_recording()
    play_waveform(waveform, device=device)
    during = gyro.stop_recording() if gyro else []

    _collect_gyro(gyro, settle_ms / 1000.0)

    if during:
        mags = [np.sqrt(s["gx"]**2 + s["gy"]**2 + s["gz"]**2) for s in during]
        return {"freq_hz": freq, "gyro_mag_mean": float(np.mean(mags)),
                "gyro_mag_max": float(np.max(mags)),
                "gyro_mag_std": float(np.std(mags)), "samples": len(during)}
    return {"freq_hz": freq, "gyro_mag_mean": 0.0, "gyro_mag_max": 0.0,
            "gyro_mag_std": 0.0, "samples": 0}


def _pick_top_n(results: list[dict], n: int = 3,
                key: str = "gyro_mag_max") -> list[dict]:
    """Return the top-N results by the given key, sorted descending."""
    ranked = sorted(results, key=lambda r: r[key], reverse=True)
    return ranked[:n]


def _plot_convergence(all_passes: list[list[dict]], title: str,
                      converged_freq: int | None = None,
                      hint_freq: int | None = None):
    """Plot all adaptive scan passes overlaid, showing convergence."""
    if not HAS_PLT:
        return
    colors = ["#9145ff", "#ff6b35", "#00cc88", "#ff3366", "#4488ff"]
    fig, ax = plt.subplots(figsize=(12, 5))
    for i, pass_data in enumerate(all_passes):
        if not any(r["gyro_mag_max"] > 0 for r in pass_data):
            continue
        c = colors[i % len(colors)]
        step = pass_data[1]["freq_hz"] - pass_data[0]["freq_hz"] if len(pass_data) > 1 else 0
        label = f"Pass {i+1} (step={step} Hz)"
        ax.plot([r["freq_hz"]/1000 for r in pass_data],
                [r["gyro_mag_max"] for r in pass_data],
                "o-", color=c, linewidth=1.2, markersize=4, label=label, alpha=0.85)
    if hint_freq:
        ax.axvline(hint_freq/1000, color="gray", linestyle=":", alpha=0.5,
                   label=f"Profile hint ({hint_freq} Hz)")
    if converged_freq:
        ax.axvline(converged_freq/1000, color="red", linestyle="--", linewidth=2,
                   alpha=0.8, label=f"Converged: {converged_freq} Hz")
    ax.set_xlabel("Frequency (kHz)")
    ax.set_ylabel("Max gyro magnitude (deg/s)")
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show(block=False)
    plt.pause(0.1)


def test_adaptive_scan(sensor: str | None = None, device: int | None = None,
                       gyro: GyroReader | None = None, dry_run: bool = False,
                       freq_min: int | None = None, freq_max: int | None = None,
                       converge_hz: int = 100) -> dict | None:
    """Adaptive convergence scan — finds the ACTUAL resonant frequency.

    Instead of stepping through a static grid, this scan:
      1. Coarse pass     — wide range, large steps, find where gyro responds
      2. Narrow pass     — zoom into top-N response peaks, finer steps
      3. Fine pass       — dial around the clear winner, ~100 Hz resolution
      4. Super-fine pass — 5 Hz steps for sub-integer precision
      5. Verify pass     — longer exposure at discovered freq to confirm

    Works in two modes:
      - Hinted: sensor name provided → starts ±5 kHz around published resonance
      - Blind:  no sensor → scans full 18–35 kHz band

    The gyro IS the feedback signal.  No acoustic reflection mic needed.
    The algorithm converges to the frequency that produces the maximum
    measured angular perturbation — whatever that turns out to be.

    Args:
        sensor:      MEMS_PROFILES key (optional — None = blind scan)
        device:      Audio output device index
        gyro:        GyroReader instance (required for real convergence)
        dry_run:     Generate waveforms only (plots pass structure)
        freq_min:    Override scan floor (Hz)
        freq_max:    Override scan ceiling (Hz)
        converge_hz: Stop narrowing when step size ≤ this (default 100 Hz)

    Returns:
        dict with {freq_hz, gyro_mag_max, gyro_mag_mean, confidence, passes}
        or None if dry_run / no gyro.
    """
    # ── Determine scan range ──
    hint_freq = None
    if sensor and sensor in MEMS_PROFILES:
        hint_freq = MEMS_PROFILES[sensor]["resonance_hz"]
        lo = freq_min or max(18000, hint_freq - 5000)
        hi = freq_max or min(35000, hint_freq + 5000)
        label = f"{sensor} (hinted @ {hint_freq} Hz)"
    else:
        lo = freq_min or 18000
        hi = freq_max or 35000
        label = "Blind Discovery" if sensor is None else f"Unknown '{sensor}'"

    print(f"\n═══ TEST: Adaptive Convergence Scan — {label} ═══")
    print(f"  Range: {lo}–{hi} Hz")
    print(f"  Converge threshold: {converge_hz} Hz step size")
    if hint_freq:
        print(f"  Profile hint: {hint_freq} Hz (will verify, not trust)")
    if not gyro and not dry_run:
        print("  ⚠ No gyro connected — running waveform-only (no convergence)")

    # ── Pass schedule ──
    # Each pass: (step_size_Hz, tone_duration_ms, settle_ms, top_n_to_keep)
    # Coarse → medium → fine, with shorter settle on coarse (speed)
    # and longer tone on fine (confidence)
    passes = []
    step = max(1000, (hi - lo) // 15)  # ~15 steps for coarse
    tone_ms = 800
    settle_ms = 300
    while step >= converge_hz:
        passes.append({"step": step, "tone_ms": tone_ms, "settle_ms": settle_ms,
                       "top_n": max(2, 5 - len(passes))})  # narrow top-N as we zoom
        step = max(converge_hz, step // 4)
        tone_ms = min(2000, tone_ms + 300)
        settle_ms = min(600, settle_ms + 100)
        if step == converge_hz and len(passes) > 1 and passes[-1]["step"] == converge_hz:
            break  # already at floor

    # Super-fine pass: 5 Hz steps for sub-integer resonance precision.
    # MEMS resonance is determined by physical geometry + manufacturing
    # tolerances — the true peak is almost certainly not a round number.
    # On a high-Q resonator, even 50 Hz off-peak measurably reduces
    # coupling efficiency.  This pass costs ~20-30s but narrows from
    # ±100 Hz to ±2.5 Hz.
    if converge_hz <= 100:
        passes.append({"step": 5, "tone_ms": 2000, "settle_ms": 600,
                       "top_n": 2})

    print(f"  Pass schedule: {len(passes)} passes")
    for i, p in enumerate(passes):
        print(f"    Pass {i+1}: step={p['step']} Hz, tone={p['tone_ms']}ms, "
              f"settle={p['settle_ms']}ms, top_n={p['top_n']}")

    all_passes_data = []
    current_lo = lo
    current_hi = hi

    for pass_idx, p_cfg in enumerate(passes):
        step = p_cfg["step"]
        freqs = list(range(current_lo, current_hi + step, step))
        # Clamp to valid range
        freqs = [f for f in freqs if 18000 <= f <= 48000]
        if not freqs:
            break

        print(f"\n  ── Pass {pass_idx+1}/{len(passes)}: "
              f"{freqs[0]}–{freqs[-1]} Hz, step={step} Hz "
              f"({len(freqs)} points) ──", flush=True)

        pass_results = []
        for freq in freqs:
            if dry_run:
                pass_results.append({"freq_hz": freq, "gyro_mag_mean": 0.0,
                                     "gyro_mag_max": 0.0, "gyro_mag_std": 0.0,
                                     "samples": 0})
                continue

            result = _emit_and_measure(freq, p_cfg["tone_ms"], device, gyro,
                                       p_cfg["settle_ms"])
            pass_results.append(result)
            if result["samples"] > 0:
                print(f"    {freq:6d} Hz → max={result['gyro_mag_max']:.4f}  "
                      f"mean={result['gyro_mag_mean']:.4f}  "
                      f"std={result['gyro_mag_std']:.4f}", flush=True)
            else:
                print(f"    {freq:6d} Hz → (no gyro data)", flush=True)

        all_passes_data.append(pass_results)

        # Find top-N peaks for next pass
        top = _pick_top_n(pass_results, n=p_cfg["top_n"])
        if not top or all(t["gyro_mag_max"] == 0 for t in top):
            print("    No valid response — continuing with same range")
            continue

        # Next pass range: span the top-N peaks ± one step width as margin
        peak_freqs = [t["freq_hz"] for t in top]
        margin = step  # one full step on each side
        current_lo = max(18000, min(peak_freqs) - margin)
        current_hi = min(48000, max(peak_freqs) + margin)

        best = top[0]
        print(f"    Best this pass: {best['freq_hz']} Hz "
              f"(max={best['gyro_mag_max']:.4f})")
        print(f"    Next window: {current_lo}–{current_hi} Hz")

    # ── Verification pass ──
    # Longer exposure at the discovered peak to confirm it's real
    converged_freq = None
    confidence = 0.0
    verify_result = None

    if not dry_run and all_passes_data:
        # Collect all results, find the global best
        all_results = [r for pdata in all_passes_data for r in pdata if r["samples"] > 0]
        if all_results:
            global_best = max(all_results, key=lambda r: r["gyro_mag_max"])
            converged_freq = global_best["freq_hz"]

            print(f"\n  ── Verification: {converged_freq} Hz (3s sustained) ──")
            verify_result = _emit_and_measure(converged_freq, 3000, device, gyro, 800)

            if verify_result["samples"] > 0:
                # Confidence = how much the peak stands out from the noise
                # Compare against baseline (lowest response across all passes)
                all_maxes = [r["gyro_mag_max"] for r in all_results]
                floor = np.percentile(all_maxes, 25)
                peak = verify_result["gyro_mag_max"]
                if floor > 0:
                    snr = peak / floor
                    confidence = min(1.0, max(0.0, (snr - 1.0) / 4.0))
                else:
                    confidence = 0.9 if peak > 0 else 0.0

                print(f"    Verified: max={verify_result['gyro_mag_max']:.4f}  "
                      f"mean={verify_result['gyro_mag_mean']:.4f}  "
                      f"confidence={confidence:.2f}")
                if hint_freq:
                    drift = converged_freq - hint_freq
                    print(f"    Drift from published: {drift:+d} Hz "
                          f"({'higher' if drift > 0 else 'lower'})")
            else:
                print(f"    (no gyro data for verification)")

    # ── Save & Plot ──
    scan_label = sensor or "blind"
    save_params = {
        "mode": "adaptive_convergence",
        "sensor": sensor, "hint_freq": hint_freq,
        "range": [lo, hi], "converge_hz": converge_hz,
        "passes": len(all_passes_data),
        "converged_freq": converged_freq, "confidence": confidence,
    }
    save_result(f"adaptive_scan_{scan_label}", save_params, None)

    _plot_convergence(all_passes_data, f"Adaptive Scan — {label}",
                      converged_freq, hint_freq)

    if converged_freq:
        print(f"\n  ╔═══════════════════════════════════════════╗")
        print(f"  ║  Discovered resonance: {converged_freq:6d} Hz          ║")
        print(f"  ║  Confidence:           {confidence:5.2f}              ║")
        if hint_freq:
            print(f"  ║  Published:            {hint_freq:6d} Hz          ║")
            print(f"  ║  Drift:                {converged_freq - hint_freq:+5d} Hz           ║")
        print(f"  ╚═══════════════════════════════════════════╝")

        return {"freq_hz": converged_freq,
                "gyro_mag_max": verify_result["gyro_mag_max"] if verify_result else 0,
                "gyro_mag_mean": verify_result["gyro_mag_mean"] if verify_result else 0,
                "confidence": confidence,
                "passes": len(all_passes_data)}

    if dry_run:
        print("\n  (dry run — convergence requires live gyro feedback)")
    return None


# Keep backward-compatible alias
def test_frequency_scan(sensor: str, device: int | None = None,
                        gyro: GyroReader | None = None, dry_run: bool = False):
    """Backward-compatible wrapper — routes to adaptive scan."""
    return test_adaptive_scan(sensor=sensor, device=device, gyro=gyro, dry_run=dry_run)


def test_ladder_walk(sensor: str, device: int | None = None,
                     gyro: GyroReader | None = None, dry_run: bool = False,
                     override_freq: int | None = None):
    """Walk through all SubharmonicLadder zones, demonstrating graduated engagement.

    Plays each zone's multi-tone stack for 3 seconds, with pauses between.
    Shows how adding more subharmonic tones progressively increases disruption.

    If override_freq is set (e.g. from adaptive scan), uses that as the
    ladder base frequency instead of the published profile value.
    """
    if sensor not in MEMS_PROFILES:
        print(f"  ERROR: Unknown sensor '{sensor}'")
        return

    published = MEMS_PROFILES[sensor]["resonance_hz"]
    base_freq = override_freq or published
    ladder = SubharmonicLadder(base_freq_hz=base_freq, sample_rate=SAMPLE_RATE)

    source = f"discovered" if override_freq else "published"
    print(f"\n═══ TEST: SubharmonicLadder Walk — {sensor} ═══")
    print(f"  Base frequency: {base_freq} Hz ({source})")
    if override_freq and override_freq != published:
        print(f"  Published was: {published} Hz (drift: {base_freq - published:+d} Hz)")
    print(f"  Zones: {len(ladder.zones)}")
    for zone in ladder.zones:
        freqs = ladder.get_zone_frequencies(zone)
        freq_strs = [f"{f:.0f}" for f in freqs]
        print(f"    {zone.name:12s}  {zone.range_min_m:5.0f}–{zone.range_max_m:5.0f}m  "
              f"divisors={zone.divisors}  freqs=[{', '.join(freq_strs)}] Hz  "
              f"mode={zone.mode}")

    all_results = {}

    for zone in ladder.zones:
        freqs = ladder.get_zone_frequencies(zone)
        freq_strs = [f"{f:.0f}" for f in freqs]
        print(f"\n  ── Zone: {zone.name} (f÷{zone.divisors}) ──")
        print(f"    Frequencies: [{', '.join(freq_strs)}] Hz")
        print(f"    Mode: {zone.mode}, weights: {zone.amplitude_weights}")

        waveform = ladder.generate_stacked_waveform(zone, duration_ms=3000)
        params = {"zone": zone.name, "divisors": zone.divisors,
                  "freqs_hz": [f for f in freqs], "mode": zone.mode}

        plot_waveform(waveform, f"Ladder Zone: {zone.name} — {freq_strs} Hz")

        if dry_run:
            save_result(f"ladder_{zone.name}_{sensor}", params, None, waveform)
            continue

        # 2s baseline → 3s emission → 2s recovery
        print("    Baseline (2s)...")
        pre = _collect_gyro(gyro, 2.0)

        print(f"    Emitting (3s)...")
        attack_t0 = time.monotonic()
        if gyro:
            gyro.start_recording()
        play_waveform(waveform, device=device)
        attack_t1 = time.monotonic()
        during = gyro.stop_recording() if gyro else []

        print("    Recovery (2s)...")
        post = _collect_gyro(gyro, 2.0)

        all_data = pre + during + post
        save_result(f"ladder_{zone.name}_{sensor}", params, all_data, waveform)

        if during:
            mags = [np.sqrt(s["gx"]**2 + s["gy"]**2 + s["gz"]**2) for s in during]
            all_results[zone.name] = {"mean": float(np.mean(mags)),
                                       "max": float(np.max(mags)),
                                       "std": float(np.std(mags))}
            print(f"    Response: mean={all_results[zone.name]['mean']:.4f}  "
                  f"max={all_results[zone.name]['max']:.4f} deg/s")

        if all_data:
            plot_gyro_data(all_data, f"Ladder Zone: {zone.name}",
                           attack_t0, attack_t1)

    # Summary comparison
    if all_results:
        print("\n  ── Ladder Summary ──")
        print(f"  {'Zone':<14s}  {'Mean':>8s}  {'Max':>8s}  {'StdDev':>8s}")
        for name, r in all_results.items():
            print(f"  {name:<14s}  {r['mean']:8.4f}  {r['max']:8.4f}  {r['std']:8.4f}")


def test_single_vs_multi(sensor: str, device: int | None = None,
                         gyro: GyroReader | None = None, dry_run: bool = False,
                         override_freq: int | None = None):
    """Compare single-frequency attack vs SubharmonicLadder multi-tone.

    This is the key research question: does the multi-tone ladder
    approach produce MORE gyro disruption than a single tone at the
    resonant frequency?  If not, the ladder is unnecessary complexity.

    If override_freq is set (from adaptive scan), uses that instead of
    the published profile value — ensures comparison uses the REAL peak.
    """
    if sensor not in MEMS_PROFILES:
        print(f"  ERROR: Unknown sensor '{sensor}'")
        return

    published = MEMS_PROFILES[sensor]["resonance_hz"]
    base_freq = override_freq or published
    source = f"discovered" if override_freq else "published"
    print(f"\n═══ TEST: Single vs Multi-Tone — {sensor} ({base_freq} Hz, {source}) ═══")
    if override_freq and override_freq != published:
        print(f"  Published was: {published} Hz (drift: {base_freq - published:+d} Hz)")
    print("  Compares: pure resonance burst vs full ladder 'kill' zone")

    # Test A: pure tone at resonance, 3 seconds
    print("\n  ─ Test A: Single frequency (pure resonance) ─")
    cfg_single = BurstConfig(
        freq_start=base_freq, freq_end=base_freq,
        pulse_ms=3.0, rise_ms=0.05, rep_rate_hz=100,
        train_duration_ms=3000, sample_rate=SAMPLE_RATE, amplitude=1.0,
    )
    wv_single = generate_burst_train(cfg_single)
    plot_waveform(wv_single, f"Single Tone — {base_freq} Hz")

    # Test B: full ladder kill zone, 3 seconds
    print("\n  ─ Test B: Multi-tone (SubharmonicLadder kill zone) ─")
    ladder = SubharmonicLadder(base_freq_hz=base_freq, sample_rate=SAMPLE_RATE)
    kill_zone = ladder.zones[-1]  # last zone = kill
    wv_multi = ladder.generate_stacked_waveform(kill_zone, duration_ms=3000)
    freqs = ladder.get_zone_frequencies(kill_zone)
    plot_waveform(wv_multi, f"Multi-Tone Kill — {[f'{f:.0f}' for f in freqs]} Hz")

    if dry_run:
        save_result(f"single_vs_multi_{sensor}",
                    {"sensor": sensor, "base_freq": base_freq}, None)
        return

    results = {}

    for label, wv in [("single", wv_single), ("multi", wv_multi)]:
        print(f"\n  Running {label}...")
        pre = _collect_gyro(gyro, 2.0)

        attack_t0 = time.monotonic()
        if gyro:
            gyro.start_recording()
        play_waveform(wv, device=device)
        attack_t1 = time.monotonic()
        during = gyro.stop_recording() if gyro else []

        post = _collect_gyro(gyro, 2.0)
        all_data = pre + during + post

        if during:
            mags = [np.sqrt(s["gx"]**2 + s["gy"]**2 + s["gz"]**2) for s in during]
            results[label] = {"mean": float(np.mean(mags)),
                              "max": float(np.max(mags))}
            print(f"    {label}: mean={results[label]['mean']:.4f}  "
                  f"max={results[label]['max']:.4f} deg/s")

        if all_data:
            plot_gyro_data(all_data, f"{label.title()} Tone — Gyro Response",
                           attack_t0, attack_t1)

        # Pause between tests to let the sensor settle
        print("  Settling (3s)...")
        time.sleep(3.0)

    if results:
        save_result(f"single_vs_multi_{sensor}",
                    {"sensor": sensor, "results": results}, None)
        print(f"\n  ── Comparison ──")
        for label, r in results.items():
            print(f"  {label:>8s}: mean={r['mean']:.4f}  max={r['max']:.4f} deg/s")
        if "single" in results and "multi" in results:
            ratio = results["multi"]["max"] / max(results["single"]["max"], 1e-9)
            print(f"  Multi/Single ratio: {ratio:.2f}x")


# ═══════════════════════════════════════════════════════════════
#  Interactive Menu
# ═══════════════════════════════════════════════════════════════

def interactive_menu():
    """Main interactive test menu."""
    print("╔══════════════════════════════════════════════╗")
    print("║     SoulMusic — Bench Test Rig              ║")
    print("║     MEMS Gyroscope Acoustic Resonance       ║")
    print("╚══════════════════════════════════════════════╝")

    # Check dependencies
    print("\n── Dependencies ──")
    print(f"  sounddevice: {'✓' if HAS_SD else '✗ (pip install sounddevice)'}")
    print(f"  pyserial:    {'✓' if HAS_SERIAL else '✗ (pip install pyserial) — gyro logging disabled'}")
    print(f"  matplotlib:  {'✓' if HAS_PLT else '✗ (pip install matplotlib) — plots disabled'}")

    if HAS_SD:
        list_audio_devices()
    list_serial_ports()

    # Setup
    device = None
    gyro = None

    if HAS_SD:
        dev_input = input("Audio output device index [default]: ").strip()
        if dev_input:
            device = int(dev_input)

    if HAS_SERIAL:
        port_input = input("Gyro serial port (blank = none): ").strip()
        if port_input:
            try:
                gyro = GyroReader(port_input)
                print(f"  Gyro reader opened on {port_input}")
            except Exception as e:
                print(f"  WARNING: Could not open {port_input}: {e}")
                gyro = None

    sensor = input(f"Target MEMS sensor [{', '.join(MEMS_PROFILES.keys())}]\n  (blank = MPU-6050): ").strip()
    if not sensor:
        sensor = "MPU-6050"
    if sensor not in MEMS_PROFILES:
        print(f"  WARNING: '{sensor}' not in profiles — using MPU-6050")
        sensor = "MPU-6050"

    print(f"\n  Sensor: {sensor} ({MEMS_PROFILES[sensor]['resonance_hz']} Hz)")
    print(f"  Audio device: {device or 'default'}")
    print(f"  Gyro: {port_input if gyro else 'none (waveform-only mode)'}")

    # Track discovered resonance — adaptive scan feeds this forward
    discovered_freq = None

    def _effective_freq() -> int:
        """Use discovered frequency if available, else profile default."""
        if discovered_freq:
            return discovered_freq
        return MEMS_PROFILES[sensor]["resonance_hz"]

    while True:
        freq_display = (f"{discovered_freq} Hz (discovered)"
                        if discovered_freq
                        else f"{MEMS_PROFILES[sensor]['resonance_hz']} Hz (published)")
        print(f"\n── Tests ── (active freq: {freq_display})")
        print("  [1] Baseline (no emission, measure gyro noise floor)")
        print("  [2] Broadband Sweep (18–35 kHz chirp)")
        print("  [3] Targeted Burst (impulse at active freq)")
        print("  [4] Adaptive Scan (hinted — converge around profile)")
        print("  [5] Blind Discovery (no hint — full 18–35 kHz adaptive)")
        print("  [6] SubharmonicLadder Zone Walk (uses active freq)")
        print("  [7] Single vs Multi-Tone Comparison (uses active freq)")
        print("  [8] Full Adaptive Suite (baseline → discover → burst → ladder → compare)")
        print("  [d] Dry Run Full Suite (generate + plot, no audio)")
        print("  [q] Quit")

        choice = input("\n  Choice: ").strip().lower()

        if choice == "1":
            test_baseline(gyro)
        elif choice == "2":
            test_broadband_sweep(device, gyro)
        elif choice == "3":
            test_targeted_burst(sensor, device, gyro)
        elif choice == "4":
            result = test_adaptive_scan(sensor=sensor, device=device, gyro=gyro)
            if result and result.get("confidence", 0) > 0.3:
                discovered_freq = result["freq_hz"]
                print(f"  → Active frequency updated to {discovered_freq} Hz")
        elif choice == "5":
            result = test_adaptive_scan(sensor=None, device=device, gyro=gyro)
            if result and result.get("confidence", 0) > 0.3:
                discovered_freq = result["freq_hz"]
                print(f"  → Active frequency updated to {discovered_freq} Hz")
        elif choice == "6":
            test_ladder_walk(sensor, device, gyro,
                             override_freq=discovered_freq)
        elif choice == "7":
            test_single_vs_multi(sensor, device, gyro,
                                 override_freq=discovered_freq)
        elif choice == "8":
            test_baseline(gyro)
            result = test_adaptive_scan(sensor=sensor, device=device, gyro=gyro)
            if result and result.get("confidence", 0) > 0.3:
                discovered_freq = result["freq_hz"]
                print(f"  → Active frequency updated to {discovered_freq} Hz")
            test_targeted_burst(sensor, device, gyro)
            test_ladder_walk(sensor, device, gyro,
                             override_freq=discovered_freq)
            test_single_vs_multi(sensor, device, gyro,
                                 override_freq=discovered_freq)
            print("\n═══ FULL ADAPTIVE SUITE COMPLETE ═══")
        elif choice == "d":
            test_adaptive_scan(sensor=sensor, device=device, gyro=gyro, dry_run=True)
            test_targeted_burst(sensor, device, gyro, dry_run=True)
            test_ladder_walk(sensor, device, gyro, dry_run=True)
            test_single_vs_multi(sensor, device, gyro, dry_run=True)
            print("\n═══ DRY RUN COMPLETE ═══")
        elif choice == "q":
            break
        else:
            print("  Invalid choice.")

    if gyro:
        gyro.close()
    print("\nDone.")


# ═══════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="SoulMusic MEMS Gyroscope Acoustic Resonance Bench Test")
    parser.add_argument("--list-devices", action="store_true",
                        help="List audio output devices and exit")
    parser.add_argument("--sensor", default="MPU-6050",
                        help=f"Target sensor model (default: MPU-6050). "
                             f"Options: {', '.join(MEMS_PROFILES.keys())}")
    parser.add_argument("--sweep", action="store_true",
                        help="Run broadband sweep test")
    parser.add_argument("--burst", metavar="SENSOR",
                        help="Run targeted burst test for SENSOR")
    parser.add_argument("--scan", metavar="SENSOR",
                        help="Run adaptive convergence scan (hinted by SENSOR)")
    parser.add_argument("--discover", action="store_true",
                        help="Run blind discovery scan (full 18–35 kHz, no sensor hint)")
    parser.add_argument("--ladder", metavar="SENSOR",
                        help="Run SubharmonicLadder walk for SENSOR")
    parser.add_argument("--compare", metavar="SENSOR",
                        help="Run single vs multi-tone comparison")
    parser.add_argument("--device", type=int, default=None,
                        help="Audio output device index")
    parser.add_argument("--gyro-port", default=None,
                        help="Serial port for gyro reader (e.g. COM3, /dev/ttyUSB0)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate waveforms and plot, no audio output")

    args = parser.parse_args()

    if args.list_devices:
        list_audio_devices()
        list_serial_ports()
        return

    # If no specific test flags, launch interactive menu
    if not any([args.sweep, args.burst, args.scan, args.discover, args.ladder, args.compare]):
        interactive_menu()
        return

    # Setup gyro if port provided
    gyro = None
    if args.gyro_port and HAS_SERIAL:
        try:
            gyro = GyroReader(args.gyro_port)
        except Exception as e:
            print(f"WARNING: Could not open gyro port: {e}")

    # Run requested tests
    if args.sweep:
        test_broadband_sweep(args.device, gyro, args.dry_run)
    if args.burst:
        test_targeted_burst(args.burst, args.device, gyro, args.dry_run)
    discovered = None
    if args.discover:
        result = test_adaptive_scan(sensor=None, device=args.device, gyro=gyro,
                                    dry_run=args.dry_run)
        if result:
            discovered = result["freq_hz"]
    if args.scan:
        result = test_adaptive_scan(sensor=args.scan, device=args.device, gyro=gyro,
                                    dry_run=args.dry_run)
        if result:
            discovered = result["freq_hz"]
    if args.ladder:
        test_ladder_walk(args.ladder, args.device, gyro, args.dry_run,
                         override_freq=discovered)
    if args.compare:
        test_single_vs_multi(args.compare, args.device, gyro, args.dry_run,
                             override_freq=discovered)

    if gyro:
        gyro.close()

    if HAS_PLT:
        input("\nPress Enter to close plots...")
        plt.close("all")


if __name__ == "__main__":
    main()
