"""
SoulMusic — acoustic/resonance.py
Waveform generator for MEMS gyroscope acoustic resonance research.

Two operating modes:
  1. CONTINUOUS SWEEP — chirp across ultrasonic range (soft targets, research)
  2. IMPULSE BURST — short high-peak pulses at resonant frequency (hardened targets)

The impulse approach exploits MEMS high Q-factor (~10,000–30,000): a single
short burst at the resonant frequency causes the proof mass to ring for
thousands of cycles on its own.  Peak SPL is 10–20 dB higher than continuous
at the same average power, and mechanical shock propagates through protective
enclosures via structural vibration rather than air coupling alone.

Reference frequencies (from published research):
  - InvenSense MPU-6050:  ~27 kHz resonant
  - InvenSense MPU-6500:  ~26 kHz resonant
  - InvenSense MPU-9250:  ~27 kHz resonant
  - InvenSense ICM-20689: ~24 kHz resonant
  - Bosch BMI055:         ~22 kHz resonant
  - Bosch BMI088:         ~23 kHz resonant
  - STMicro LSM6DS3:      ~20 kHz resonant
  - TDK/InvenSense IIM-42652: ~25 kHz resonant
"""

import numpy as np
from dataclasses import dataclass

# Speed of sound in air at ~20°C (m/s).  Used by Doppler pre-compensation
# to shift emitted frequencies so the moving target receives f_resonance.
SPEED_OF_SOUND = 343.0


def doppler_precompensate(freq_hz: float, radial_speed_ms: float) -> float:
    """Pre-shift an emission frequency for a moving target.

    When a target moves toward/away from a stationary emitter, the
    target receives a Doppler-shifted frequency.  This function
    returns the frequency to *emit* so the target hears ``freq_hz``.

    Physics (stationary source, moving receiver):
        f_received = f_emitted × (c + v) / c
    Solving for f_emitted:
        f_emitted = f_received × c / (c + v)

    Sign convention:
        v > 0 → target approaching (emit *lower* so it hears the right freq)
        v < 0 → target receding   (emit *higher*)
        v = 0 → no correction

    Edge case: |v| >= c is physically meaningless for acoustic signals;
    we clamp to avoid division by zero or negative results.

    Args:
        freq_hz:  The frequency the target must *receive* (MEMS resonance).
        radial_speed_ms: Target's radial velocity in m/s (positive = approaching).

    Returns:
        The frequency to emit (Hz), always > 0.
    """
    if abs(radial_speed_ms) < 0.01:
        return freq_hz
    # Clamp to ±0.95c — beyond this is supersonic and our model breaks
    v = max(-SPEED_OF_SOUND * 0.95, min(SPEED_OF_SOUND * 0.95, radial_speed_ms))
    return freq_hz * SPEED_OF_SOUND / (SPEED_OF_SOUND + v)


@dataclass
class SweepConfig:
    """Configuration for an acoustic resonance sweep."""
    freq_start: int = 18000    # Hz — start of chirp
    freq_end: int = 35000      # Hz — end of chirp
    duration_ms: int = 100     # sweep duration in milliseconds
    sample_rate: int = 96000   # output sample rate (must be ≥ 2x freq_end)
    amplitude: float = 0.8     # 0.0–1.0 output amplitude
    window: str = "hann"       # envelope window: "none", "hann", "tukey"
    repeat: int = 1            # number of consecutive sweeps in buffer


def generate_chirp(config: SweepConfig) -> np.ndarray:
    """Generate a linear frequency chirp waveform.

    Returns a float32 numpy array of samples, values in [-amplitude, +amplitude].
    Each sample at index n has instantaneous frequency:
        f(t) = f_start + (f_end - f_start) * t / duration
    Phase is the integral of frequency:
        φ(t) = 2π * (f_start * t + (f_end - f_start) * t² / (2 * duration))
    """
    sr = config.sample_rate
    duration_s = config.duration_ms / 1000.0
    n_samples = int(sr * duration_s)

    if n_samples == 0:
        return np.array([], dtype=np.float32)

    t = np.linspace(0, duration_s, n_samples, endpoint=False, dtype=np.float64)

    # Linear chirp: instantaneous frequency ramps linearly
    f0 = config.freq_start
    f1 = config.freq_end
    chirp_rate = (f1 - f0) / duration_s

    # Phase = 2π ∫ f(t) dt = 2π * (f0*t + chirp_rate*t²/2)
    phase = 2.0 * np.pi * (f0 * t + 0.5 * chirp_rate * t * t)
    waveform = np.sin(phase).astype(np.float32)

    # Apply amplitude envelope window
    if config.window == "hann":
        window = np.hanning(n_samples).astype(np.float32)
        waveform *= window
    elif config.window == "tukey":
        # Tukey window — flat top, tapered edges (10% taper)
        from scipy.signal import windows
        window = windows.tukey(n_samples, alpha=0.1).astype(np.float32)
        waveform *= window
    # "none" = no windowing

    waveform *= config.amplitude

    # Repeat if requested
    if config.repeat > 1:
        waveform = np.tile(waveform, config.repeat)

    return waveform


def generate_targeted_chirp(center_freq: int, bandwidth: int = 2000,
                            config: SweepConfig | None = None) -> np.ndarray:
    """Generate a narrow chirp centered on a specific resonant frequency.

    Useful when the target MEMS sensor model is known — sweep a narrow
    band around its resonance for maximum energy coupling.

    Args:
        center_freq: Known resonant frequency of target MEMS sensor (Hz)
        bandwidth: Total sweep width in Hz (centered on center_freq)
        config: Base config (freq_start/end will be overridden)
    """
    if config is None:
        config = SweepConfig()
    config.freq_start = center_freq - bandwidth // 2
    config.freq_end = center_freq + bandwidth // 2
    return generate_chirp(config)


# ── Known MEMS sensor resonant frequencies ──
#
# Field reference:
#   resonance_hz        — Gyroscope proof-mass resonant frequency (Hz), nominal at 25°C.
#                         Used as the primary targeting frequency.
#   manufacturer        — Chip manufacturer.
#   accel_resonance_hz  — Accelerometer proof-mass resonant frequency (Hz), where
#                         documented.  Accelerometer proof masses are heavier / less stiff
#                         → lower resonance (1–10 kHz).  Present only on sensors where
#                         the accel die is confirmed separate (e.g. BMI088 dual-die).
#                         None = not independently documented or co-located with gyro die.
#   axis_resonances_hz  — Per-axis gyro resonances [X, Y, Z] (Hz), where axes differ
#                         measurably.  Datasheet and teardown values from testsubjects.md.
#                         A single-axis targeted sweep may miss other axes by up to 4 kHz.
#   mfg_tolerance_pct   — ±Percentage manufacturing spread (testsubjects.md: ±5–15%).
#                         A targeted chirp must span ≥ manufacturing_bandwidth() to cover
#                         any individual unit of this model.
#   temp_coeff_ppm_per_c— Resonance temperature coefficient (ppm/°C).  Silicon stiffness
#                         decreases with heat → resonance drops (negative sign typical).
#                         Default: −50 ppm/°C.  See thermal_compensate_resonance().

MEMS_PROFILES = {
    # ── InvenSense / TDK ──────────────────────────────────────────
    "MPU-6050": {
        "resonance_hz": 27000,
        "manufacturer": "InvenSense",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [27000, 23000, 28000],  # X ~27k, Y ~23k, Z ~28k
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "MPU-6500": {
        "resonance_hz": 26000,
        "manufacturer": "InvenSense",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [26000, 26000, 26000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "MPU-9250": {
        "resonance_hz": 27000,
        "manufacturer": "InvenSense",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [27000, 27000, 27000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "ICM-20689": {
        "resonance_hz": 24000,
        "manufacturer": "InvenSense",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [24000, 24000, 24000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "ICM-20602": {
        "resonance_hz": 24000,
        "manufacturer": "InvenSense",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [24000, 24000, 24000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "ICM-42688-P": {
        "resonance_hz": 25000,
        "manufacturer": "TDK/InvenSense",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [25000, 21000, 25000],  # Y-axis lower per testsubjects
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "ICM-42670-P": {
        "resonance_hz": 21000,
        "manufacturer": "TDK/InvenSense",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [21000, 21000, 21000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "IIM-42652": {
        "resonance_hz": 25000,
        "manufacturer": "TDK/InvenSense",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [25000, 25000, 25000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    # ── Bosch ────────────────────────────────────────────────────
    "BMI055": {
        "resonance_hz": 22000,
        "manufacturer": "Bosch",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [22000, 22000, 22000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "BMI088": {
        "resonance_hz": 23000,
        "manufacturer": "Bosch",
        # BMI088 uses a separate accelerometer die (BMA490L-family MEMS).
        # Accelerometer proof mass resonance ~6.5 kHz (confirmed in datasheet
        # self-test frequency range and teardown reports in testsubjects.md).
        # A dual-mass attack must drive BOTH bands to defeat EKF sensor fusion.
        "accel_resonance_hz": 6500,
        "axis_resonances_hz": [23000, 22000, 23500],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "BMI160": {
        "resonance_hz": 27000,
        "manufacturer": "Bosch",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [27000, 27000, 27000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "BMI270": {
        "resonance_hz": 23000,
        "manufacturer": "Bosch",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [23000, 22000, 23000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    # ── STMicroelectronics ────────────────────────────────────────
    "LSM6DS3": {
        "resonance_hz": 20000,
        "manufacturer": "STMicroelectronics",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [20000, 20000, 20000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "LSM6DSO": {
        "resonance_hz": 21000,
        "manufacturer": "STMicroelectronics",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [21000, 17000, 21000],  # Y-axis lower per testsubjects
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "LSM6DSL": {
        "resonance_hz": 18000,
        "manufacturer": "STMicroelectronics",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [18000, 18000, 18000],
        "mfg_tolerance_pct": 10,
        "temp_coeff_ppm_per_c": -50,
    },
    "LSM6DSMTR": {
        # Found in military sub-assemblies per testsubjects.md — ~17 kHz
        "resonance_hz": 17000,
        "manufacturer": "STMicroelectronics",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [17000, 17000, 17000],
        "mfg_tolerance_pct": 12,
        "temp_coeff_ppm_per_c": -50,
    },
    # ── Analog Devices (military / precision navigation) ──────────
    # Note: 14 kHz is below the passband of standard 25 kHz piezo
    # transducers.  A broadband compression driver is required to
    # reach these sensors effectively.
    "ADXRS290": {
        "resonance_hz": 14000,
        "manufacturer": "Analog Devices",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [14000, 14000, 14000],
        "mfg_tolerance_pct": 8,
        "temp_coeff_ppm_per_c": -40,
    },
    "ADXRS453": {
        "resonance_hz": 14000,
        "manufacturer": "Analog Devices",
        "accel_resonance_hz": None,
        "axis_resonances_hz": [14000, 14000, 14000],
        "mfg_tolerance_pct": 8,
        "temp_coeff_ppm_per_c": -40,
    },
}


def get_broad_sweep(duration_ms: int = 100, amplitude: float = 0.8) -> np.ndarray:
    """Quick helper: generate a broad sweep covering all known MEMS resonances."""
    return generate_chirp(SweepConfig(
        freq_start=18000,
        freq_end=35000,
        duration_ms=duration_ms,
        amplitude=amplitude,
        window="tukey",
    ))


def get_targeted_sweep(sensor_model: str, duration_ms: int = 50,
                       amplitude: float = 0.9,
                       cover_all_axes: bool = True) -> np.ndarray:
    """Generate a sweep optimally covering the resonances of a known sensor.

    Improvements over the generic ``generate_targeted_chirp``:

    **All-axis coverage** (``cover_all_axes=True``, default):
      When ``axis_resonances_hz`` is present, the sweep spans from
      ``min(axes) − 1 kHz`` to ``max(axes) + 1 kHz``.  This disrupts all
      three gyroscope axes simultaneously.  A single-axis targeted sweep
      misses axes that differ in resonance — e.g. MPU-6050 X=27 kHz vs
      Y=23 kHz: a 26–28 kHz sweep completely skips the Y-axis.

    **Tolerance-aware bandwidth** (``cover_all_axes=False``):
      Sweep bandwidth is widened to ``manufacturing_bandwidth(nominal,
      tolerance_pct)`` to cover the ±5–15% unit-to-unit variation
      documented in testsubjects.md.  The previous hardcoded ±1 kHz covers
      only ±3.7% at 27 kHz — insufficient for sensors with ±15% spread.

    Args:
        sensor_model:    Key in MEMS_PROFILES.
        duration_ms:     Sweep duration (ms).
        amplitude:       Peak amplitude (0.0–1.0).
        cover_all_axes:  If True, widen to cover axis_resonances_hz.
                         If False, use tolerance-aware single-axis bandwidth.

    Returns:
        float32 numpy array of sweep samples.
    """
    profile = MEMS_PROFILES.get(sensor_model)
    if not profile:
        raise ValueError(f"Unknown sensor model: {sensor_model}. "
                         f"Known: {list(MEMS_PROFILES.keys())}")
    axes = profile.get("axis_resonances_hz")
    if cover_all_axes and axes:
        # Span from lowest axis resonance (−1 kHz guard) to highest (+1 kHz guard)
        f_start = max(100, min(axes) - 1000)
        f_end = max(axes) + 1000
    else:
        center = profile["resonance_hz"]
        tol = profile.get("mfg_tolerance_pct", 10)
        half_bw = manufacturing_bandwidth(center, tol) // 2
        f_start = max(100, center - half_bw)
        f_end = center + half_bw
    return generate_chirp(SweepConfig(
        freq_start=f_start,
        freq_end=f_end,
        duration_ms=duration_ms,
        sample_rate=96000,
        amplitude=amplitude,
        window="tukey",
    ))


# ═══════════════════════════════════════════════════════════════
#  MODE 2: IMPULSE BURST — concentrated pulse for hardened targets
# ═══════════════════════════════════════════════════════════════

@dataclass
class BurstConfig:
    """Configuration for an impulse burst waveform.

    A burst is a short packet of ultrasonic cycles with a sharp attack
    envelope, designed to deliver maximum peak SPL and exploit the
    MEMS sensor's high Q-factor ringdown.

    The burst is repeated at `rep_rate_hz` to re-excite the proof mass
    before its natural ringdown decays.  Typical MEMS Q=10,000 at
    25 kHz gives a ringdown time of ~130ms, so repetition at 20–100 Hz
    maintains continuous disruption.
    """
    freq_start: int = 20000    # Hz — carrier start (or fixed freq if == freq_end)
    freq_end: int = 30000      # Hz — carrier end (chirp within burst)
    pulse_ms: float = 2.0      # duration of a single burst (ms)
    rise_ms: float = 0.08      # attack time (ms) — fast rise = shock content
    rep_rate_hz: int = 50      # bursts per second
    train_duration_ms: int = 1000  # total train duration (ms)
    sample_rate: int = 96000   # output sample rate
    amplitude: float = 1.0     # peak amplitude (0.0–1.0, push to max)


def generate_burst(config: BurstConfig) -> np.ndarray:
    """Generate a single impulse burst.

    The burst has a sharp exponential attack, sustain at peak, and
    abrupt cutoff.  Contains a frequency chirp from freq_start → freq_end
    (or pure tone if equal) to cover resonance uncertainty.

    Returns float32 array of one burst's samples.
    """
    sr = config.sample_rate
    pulse_s = config.pulse_ms / 1000.0
    rise_s = config.rise_ms / 1000.0
    n_samples = int(sr * pulse_s)
    n_rise = max(1, int(sr * rise_s))

    if n_samples == 0:
        return np.array([], dtype=np.float32)

    t = np.linspace(0, pulse_s, n_samples, endpoint=False, dtype=np.float64)

    # Carrier: chirp within the burst duration
    f0 = config.freq_start
    f1 = config.freq_end
    if f0 == f1:
        # Pure tone
        phase = 2.0 * np.pi * f0 * t
    else:
        # Linear chirp within the pulse
        chirp_rate = (f1 - f0) / pulse_s
        phase = 2.0 * np.pi * (f0 * t + 0.5 * chirp_rate * t * t)

    carrier = np.sin(phase).astype(np.float32)

    # Envelope: sharp exponential attack → flat sustain → hard cutoff
    envelope = np.ones(n_samples, dtype=np.float32)

    # Attack: exponential rise in n_rise samples
    # e^(-5) ≈ 0.007, so we go from ~0 to 1 in n_rise samples
    attack = 1.0 - np.exp(-5.0 * np.arange(n_rise, dtype=np.float32) / n_rise)
    envelope[:n_rise] = attack

    # No decay/release — hard cutoff maximizes shock content at the tail
    # (the abrupt stop itself generates broadband energy)

    waveform = carrier * envelope * config.amplitude
    return waveform


def generate_burst_train(config: BurstConfig) -> np.ndarray:
    """Generate a repeating pulse train of impulse bursts.

    Layout per repetition period:
        [  burst  |  silence  |  burst  |  silence  | ... ]

    The silence between bursts is critical — it's where the MEMS proof
    mass rings down on its own (Q-factor exploitation).  The next burst
    re-excites before the ringdown fully decays.

    Returns float32 array of the complete train.
    """
    sr = config.sample_rate
    train_s = config.train_duration_ms / 1000.0
    total_samples = int(sr * train_s)

    # Samples per repetition period
    period_samples = int(sr / config.rep_rate_hz)

    # Generate one burst
    burst = generate_burst(config)
    burst_len = len(burst)

    if burst_len >= period_samples:
        # Burst is longer than one period — truncate (shouldn't happen
        # with sane configs, but be safe)
        burst = burst[:period_samples]
        burst_len = period_samples

    train = np.zeros(total_samples, dtype=np.float32)
    pos = 0
    while pos + burst_len <= total_samples:
        train[pos:pos + burst_len] = burst
        pos += period_samples

    return train


def get_broad_burst(rep_rate_hz: int = 50, pulse_ms: float = 2.0,
                    train_ms: int = 1000) -> np.ndarray:
    """Broad-spectrum impulse burst covering all known MEMS resonances.

    Use when target sensor model is unknown.  The chirp within each
    2ms pulse sweeps 18–35 kHz, hitting every known resonance.
    At 50 Hz rep rate, this re-excites every 20ms — well within the
    ringdown window of any MEMS gyro with Q > 500.
    """
    return generate_burst_train(BurstConfig(
        freq_start=18000,
        freq_end=35000,
        pulse_ms=pulse_ms,
        rise_ms=0.08,
        rep_rate_hz=rep_rate_hz,
        train_duration_ms=train_ms,
        amplitude=1.0,
    ))


def get_targeted_burst(sensor_model: str, rep_rate_hz: int = 50,
                       pulse_ms: float = 3.0,
                       train_ms: int = 1000) -> np.ndarray:
    """Targeted impulse burst for a known MEMS sensor model.

    Burst bandwidth is tolerance-aware: spans ``manufacturing_bandwidth``
    (±mfg_tolerance_pct of nominal) so any individual unit of the sensor
    model is covered, not just the datasheet nominal.  The previous hardcoded
    ±1 kHz only covered ±3.7% at 27 kHz — inadequate for sensors with ±15%
    spread.

    Longer pulse (3ms default) = more cycles at resonance per burst.
    Fast attack (0.05ms rise) maximises shock content.
    """
    profile = MEMS_PROFILES.get(sensor_model)
    if not profile:
        raise ValueError(f"Unknown sensor model: {sensor_model}. "
                         f"Known: {list(MEMS_PROFILES.keys())}")
    center = profile["resonance_hz"]
    tol = profile.get("mfg_tolerance_pct", 10)
    half_bw = manufacturing_bandwidth(center, tol) // 2
    return generate_burst_train(BurstConfig(
        freq_start=center - half_bw,
        freq_end=center + half_bw,
        pulse_ms=pulse_ms,
        rise_ms=0.05,        # fast attack for maximum shock content
        rep_rate_hz=rep_rate_hz,
        train_duration_ms=train_ms,
        amplitude=1.0,
    ))


def get_shock_burst(rep_rate_hz: int = 100, pulse_ms: float = 1.0,
                    train_ms: int = 500) -> np.ndarray:
    """Maximum shock impulse — shortest pulse, fastest rep rate.

    Designed for hardened targets with acoustic enclosures.  The 1ms
    pulse with 0.05ms rise time maximizes broadband shock content —
    the enclosure's own structural resonances are excited, turning
    the shell into a transmission medium rather than a barrier.

    100 Hz rep rate = 10ms between pulses.  Each pulse is only 1ms
    on, 9ms off = 10% duty cycle.  Peak SPL is ~10 dB above what
    continuous mode could achieve at the same average power.
    """
    return generate_burst_train(BurstConfig(
        freq_start=18000,
        freq_end=35000,
        pulse_ms=pulse_ms,
        rise_ms=0.05,
        rep_rate_hz=rep_rate_hz,
        train_duration_ms=train_ms,
        amplitude=1.0,
    ))


# ═══════════════════════════════════════════════════════════════
#  PROOF-MASS PHYSICS UTILITIES
#  Real-world corrections: thermal drift, manufacturing spread,
#  Q-factor ringdown, multi-axis coverage, dual-mass attacks.
# ═══════════════════════════════════════════════════════════════

# Upper bound of human hearing used for audible subharmonic checks.
HUMAN_HEARING_HZ: int = 20000


def thermal_compensate_resonance(nominal_hz: float,
                                  delta_temp_c: float,
                                  temp_coeff_ppm_per_c: float = -50.0) -> float:
    """Adjust a MEMS proof-mass resonant frequency for temperature offset.

    MEMS resonance scales with material stiffness: f ∝ √(k/m).  Silicon
    Young's modulus decreases with temperature (~−60 ppm/°C), so resonance
    typically drops as the sensor heats up.  Typical consumer gyro tempco:
    −20 to −80 ppm/°C.  The default −50 ppm/°C is a conservative midpoint.

    Why this matters:
      A sensor at 65°C (summer electronics bay) vs −10°C (outdoor winter)
      shifts its resonance by up to 3.75 kHz at 27 kHz nominal.  A targeted
      sweep with only ±1 kHz bandwidth can miss the real resonance entirely
      in extreme conditions.  Use this function to pre-shift the center
      frequency when ambient temperature is known from onboard telemetry.

    Args:
        nominal_hz:           Nominal resonance at 25°C reference (Hz).
        delta_temp_c:         Temperature offset from 25°C.  Positive = hotter.
        temp_coeff_ppm_per_c: Frequency tempco (ppm/°C).  Negative means
                              resonance drops as temperature rises.

    Returns:
        Temperature-corrected resonant frequency (Hz).

    Examples:
        Sensor at 65°C (delta = +40°C), tempco = −50 ppm/°C:
            thermal_compensate_resonance(27000, 40, -50) → 26946 Hz
        Sensor at −10°C (delta = −35°C):
            thermal_compensate_resonance(23000, -35, -50) → 23040 Hz
    """
    shift_fraction = temp_coeff_ppm_per_c * delta_temp_c / 1_000_000.0
    return nominal_hz * (1.0 + shift_fraction)


def manufacturing_bandwidth(nominal_hz: float, tolerance_pct: float) -> int:
    """Minimum chirp bandwidth to guarantee hitting any unit of a sensor model.

    MEMS resonance frequencies vary ±tolerance_pct from the datasheet value
    due to photolithography variation, solder mass loading on the die, and
    PCB parasitic coupling.  testsubjects.md documents ±5–15% spread for
    consumer-grade sensors.  The previous hardcoded ±1 kHz in targeted
    sweeps/bursts only covers ±3.7% at 27 kHz — insufficient for sensors
    with ±15% spread (±4050 Hz at 27 kHz).

    Args:
        nominal_hz:     Datasheet resonant frequency (Hz).
        tolerance_pct:  Manufacturing variation (± % of nominal). Typical: 10.

    Returns:
        Required total chirp bandwidth in Hz (centered on nominal_hz).
        Minimum 2000 Hz.

    Example:
        manufacturing_bandwidth(27000, 10) → 5400
        A targeted chirp should span 27000 ± 2700 Hz (24300–29700 Hz)
        to guarantee hitting any MPU-6050 regardless of manufacturing lot.
    """
    return max(2000, int(2.0 * nominal_hz * tolerance_pct / 100.0))


def optimal_burst_rate_hz(f0_hz: float,
                           q_factor: float = 10000,
                           min_amplitude_fraction: float = 0.5) -> float:
    """Minimum burst rep rate to keep proof-mass amplitude above a threshold.

    After a burst, proof-mass oscillation decays exponentially:
        A(t) = A₀ × exp(−π f₀ t / Q)
    Time constant:  τ = Q / (π × f₀)

    To maintain A ≥ min_amplitude_fraction × A₀, the next burst must fire
    before the amplitude falls to that fraction:
        t_refill = τ × ln(1 / min_amplitude_fraction)
        rate_min = 1 / t_refill

    This is a **lower bound**.  Higher rep rates keep amplitude closer to
    continuous CW (better for disruption mode), at the cost of reduced peak
    amplitude per burst.  The default burst presets (50–100 Hz) run at
    6–12× the minimum — well within continuous-disruption range.

    Args:
        f0_hz:                  Proof-mass resonant frequency (Hz).
        q_factor:               Mechanical Q-factor. Consumer MEMS: 3,000–30,000.
                                Higher Q → slower ringdown → lower minimum rate.
        min_amplitude_fraction: Amplitude floor between bursts (0.0–1.0).
                                0.5 = never let amplitude drop below 50%.

    Returns:
        Minimum burst repetition rate (Hz), ≥ 1.0.

    Examples:
        MPU-6050 (f₀=27 kHz, Q=10,000):
            optimal_burst_rate_hz(27000, 10000, 0.5) → ~8.4 Hz
            Run at 3× → 25 Hz minimum; default 50 Hz = 6× margin.
        Budget MEMS (f₀=20 kHz, Q=3,000):
            optimal_burst_rate_hz(20000, 3000, 0.5) → ~28 Hz
            Higher Q requirement because lower Q decays faster.
    """
    import math
    if q_factor <= 0 or f0_hz <= 0:
        return 1.0
    tau_s = q_factor / (math.pi * f0_hz)
    clipped_frac = max(1e-9, min(0.9999, min_amplitude_fraction))
    t_refill = tau_s * math.log(1.0 / clipped_frac)
    if t_refill <= 0:
        return 1.0
    return max(1.0, 1.0 / t_refill)


def subharmonic_audible_components(base_freq_hz: int,
                                    divisors: list,
                                    threshold_hz: int = HUMAN_HEARING_HZ
                                    ) -> list:
    """Return (frequency, divisor) pairs that fall within human hearing range.

    SubharmonicLadder priming/charging zones emit at f₀/5 and f₀/2.
    For sensors resonating below ~30 kHz, these subharmonics are audible:
      - BMI088 at 23 kHz: f/5=4600 Hz, f/3=7667 Hz, f/2=11500 Hz (all audible)
      - LSM6DS3 at 20 kHz: f/5=4000 Hz, f/3=6667 Hz, f/2=10000 Hz (all audible)
      - MPU-6050 at 27 kHz: f/5=5400 Hz (audible), f/2=13500 Hz (audible)

    At high SPL, these audible tones pose operator and bystander exposure
    risks.  The operator should be aware when engagement zones emit into the
    audible band, particularly during priming at extended range where the
    signal propagates freely.

    Args:
        base_freq_hz:  Primary MEMS resonant frequency (Hz).
        divisors:      List of integer subharmonic divisors in the zone.
        threshold_hz:  Ceiling of human hearing to check against.
                       Default 20 kHz (conservative upper bound).

    Returns:
        List of (frequency_hz: float, divisor: int) tuples, sorted by frequency.
        Empty list if all subharmonics are ultrasonic.

    Example:
        subharmonic_audible_components(23000, [5, 3, 2, 1])
        → [(4600.0, 5), (7666.7, 3), (11500.0, 2)]
        (f/1 = 23000 Hz is ultrasonic and excluded)
    """
    audible = []
    for d in divisors:
        if d <= 0:
            continue
        freq = base_freq_hz / float(d)
        if freq <= threshold_hz:
            audible.append((freq, d))
    audible.sort(key=lambda x: x[0])
    return audible


def generate_dual_mass_waveform(gyro_freq_hz: int,
                                 accel_freq_hz: int,
                                 duration_ms: int = 100,
                                 sample_rate: int = 96000,
                                 gyro_amplitude: float = 0.7,
                                 accel_amplitude: float = 0.8,
                                 window: str = "tukey") -> np.ndarray:
    """Attack both gyroscope AND accelerometer proof masses simultaneously.

    Modern IMUs contain physically separate gyroscope and accelerometer proof
    masses, each with its own resonant frequency:
      - Gyroscope proof mass:     20–30 kHz (high stiffness, low mass)
      - Accelerometer proof mass: 1–10 kHz  (lower stiffness, heavier mass)

    Why this defeats EKF sensor fusion:
      ArduPilot EKF3 and PX4 EKF2 automatically down-weight a degraded sensor
      and increase reliance on redundant data.  Disrupting only the gyro leaves
      accelerometer data intact — the platform can continue flying with degraded
      but still usable attitude estimates.  Simultaneous dual-mass attack denies
      both data streams, collapsing the state estimator entirely.

    Hardware requirement:
      Standard 25 kHz piezo transducers have poor efficiency below ~15 kHz.
      Effective dual-mass attack needs a split transducer stack:
        - High element: narrowband piezo (20–35 kHz) for the gyro band
        - Low element: broadband compression driver (2–12 kHz) for the accel band
      The combined waveform returned here is suitable for a two-channel DAC
      driving these elements through separate power amplifiers.

    Args:
        gyro_freq_hz:    Gyroscope proof-mass resonant frequency (Hz).
        accel_freq_hz:   Accelerometer proof-mass resonant frequency (Hz).
        duration_ms:     Output duration (ms).
        sample_rate:     Sample rate (Hz). Must satisfy Nyquist for gyro_freq_hz.
        gyro_amplitude:  Amplitude weight for the gyro chirp (0.0–1.0).
        accel_amplitude: Amplitude weight for the accel chirp (0.0–1.0).
        window:          Envelope window ("none", "hann", "tukey").

    Returns:
        float32 numpy array normalized to peak ±1.  Both frequency bands
        are superposed — use a hardware cross-over to split them.

    Raises:
        ValueError: If sample_rate < 2 × gyro_freq_hz (Nyquist violation).
    """
    if sample_rate < 2 * gyro_freq_hz:
        raise ValueError(
            f"sample_rate {sample_rate} Hz is below Nyquist for "
            f"gyro_freq_hz {gyro_freq_hz} Hz (need ≥ {2 * gyro_freq_hz} Hz)."
        )
    # Gyro band: ±1 kHz sweep (covers ±3.7% at 27 kHz; axis spread handled
    # by caller using get_targeted_sweep with cover_all_axes=True)
    wf_gyro = generate_chirp(SweepConfig(
        freq_start=gyro_freq_hz - 1000,
        freq_end=gyro_freq_hz + 1000,
        duration_ms=duration_ms,
        sample_rate=sample_rate,
        amplitude=gyro_amplitude,
        window=window,
    ))
    # Accel band: ±300 Hz (accelerometer Q is lower, resonance broader;
    # tight window maximises energy in the accel band without bleed)
    accel_lo = max(100, accel_freq_hz - 300)
    wf_accel = generate_chirp(SweepConfig(
        freq_start=accel_lo,
        freq_end=accel_freq_hz + 300,
        duration_ms=duration_ms,
        sample_rate=sample_rate,
        amplitude=accel_amplitude,
        window=window,
    ))
    combined = wf_gyro.astype(np.float64) + wf_accel.astype(np.float64)
    peak = np.max(np.abs(combined))
    if peak > 0:
        combined /= peak
    return combined.astype(np.float32)


def get_dual_mass_sweep(sensor_model: str, duration_ms: int = 100,
                         amplitude: float = 0.9) -> np.ndarray:
    """Dual-mass attack sweep for sensors with a documented accel resonance.

    Retrieves gyroscope and accelerometer resonant frequencies from
    MEMS_PROFILES and generates a combined waveform targeting both proof
    masses.  Currently only BMI088 has a documented accel_resonance_hz.

    Args:
        sensor_model: Key in MEMS_PROFILES (must have 'accel_resonance_hz').
        duration_ms:  Waveform duration (ms).
        amplitude:    Peak amplitude applied to both gyro and accel bands.

    Raises:
        ValueError: Unknown sensor, or sensor has no documented accel resonance.
    """
    profile = MEMS_PROFILES.get(sensor_model)
    if not profile:
        raise ValueError(
            f"Unknown sensor model: {sensor_model}. "
            f"Known: {list(MEMS_PROFILES.keys())}"
        )
    accel_hz = profile.get("accel_resonance_hz")
    if not accel_hz:
        dual_capable = [k for k, v in MEMS_PROFILES.items()
                        if v.get("accel_resonance_hz")]
        raise ValueError(
            f"Sensor '{sensor_model}' has no documented accel_resonance_hz.  "
            f"Dual-mass attack requires: {dual_capable}"
        )
    return generate_dual_mass_waveform(
        gyro_freq_hz=profile["resonance_hz"],
        accel_freq_hz=accel_hz,
        duration_ms=duration_ms,
        gyro_amplitude=amplitude,
        accel_amplitude=amplitude,
    )


# ═══════════════════════════════════════════════════════════════
#  MODE 3: SUBHARMONIC LADDER — graduated multi-frequency
#  parametric resonance attack for extended range engagement
# ═══════════════════════════════════════════════════════════════

@dataclass
class EngagementZone:
    """A single zone in the subharmonic engagement ladder.

    Each zone defines a range bracket and the set of subharmonic
    frequencies to transmit within that bracket.  Frequencies are
    expressed as divisors of the target MEMS resonant frequency.
    """
    name: str
    range_max_m: float          # outer boundary (farther from emitter)
    range_min_m: float          # inner boundary (closer to emitter)
    divisors: list              # subharmonic divisors active in this zone
    amplitude_weights: list     # per-divisor amplitude (0.0–1.0), same length
    mode: str = "continuous"    # "continuous" (CW) or "burst"
    rep_rate_hz: int = 50       # burst rep rate (if burst mode)
    pulse_ms: float = 2.0       # burst pulse width (if burst mode)


class SubharmonicLadder:
    """Graduated engagement system that stacks subharmonic frequencies
    as a target closes range, exploiting parametric resonance and
    nonlinear intermodulation to build MEMS disruption from extreme
    distance.

    The ladder is defined by a base MEMS resonant frequency (f₀) and
    a series of engagement zones.  Each zone adds subharmonic tones at
    integer divisors of f₀.  As the target closes range, more
    frequencies are stacked — the MEMS accumulates energy from all
    subharmonics simultaneously.

    Physics exploited:
      - Atmospheric absorption drops ~50× from f₀ to f₀/5, enabling
        long-range priming at minimal power cost.
      - Multi-frequency parametric drive widens the Mathieu instability
        boundary, lowering the amplitude threshold for resonance.
      - Nonlinear intermodulation inside the MEMS proof mass generates
        combinations that land at or near f₀, creating resonance excitation
        that never traveled through the atmosphere at f₀'s absorption rate.
    """

    def __init__(self, base_freq_hz: int = 25000,
                 sample_rate: int = 96000):
        self.base_freq_hz = base_freq_hz
        self.sample_rate = sample_rate
        self.zones: list[EngagementZone] = []
        self._build_default_zones()

    def _build_default_zones(self):
        """Build the default 4-zone engagement ladder.

        Zone 1 (Priming):    200–120m  →  f/5 continuous
        Zone 2 (Charging):   120–60m   →  f/5 + f/2 continuous
        Zone 3 (Disruption): 60–25m    →  f/5 + f/3 + f/2 burst
        Zone 4 (Kill):       25–0m     →  f/5 + f/3 + f/2 + f direct burst
        """
        self.zones = [
            EngagementZone(
                name="priming",
                range_max_m=200.0,
                range_min_m=120.0,
                divisors=[5],
                amplitude_weights=[1.0],
                mode="continuous",
            ),
            EngagementZone(
                name="charging",
                range_max_m=120.0,
                range_min_m=60.0,
                divisors=[5, 2],
                amplitude_weights=[0.6, 1.0],
                mode="continuous",
            ),
            EngagementZone(
                name="disruption",
                range_max_m=60.0,
                range_min_m=25.0,
                divisors=[5, 3, 2],
                amplitude_weights=[0.4, 0.7, 1.0],
                mode="burst",
                rep_rate_hz=50,
                pulse_ms=3.0,
            ),
            EngagementZone(
                name="kill",
                range_max_m=25.0,
                range_min_m=0.0,
                divisors=[5, 3, 2, 1],
                amplitude_weights=[0.3, 0.5, 0.8, 1.0],
                mode="burst",
                rep_rate_hz=100,
                pulse_ms=2.0,
            ),
        ]

    def retune(self, new_base_freq_hz: int):
        """Retune the entire ladder for a different MEMS resonant frequency.

        Called when shell detection or platform ID reveals the actual f₀.
        All zone frequencies recalculate automatically since they're
        defined as ratios (divisors), not absolute frequencies.
        """
        self.base_freq_hz = new_base_freq_hz

    @staticmethod
    def validate_zone_config(zone: "EngagementZone"):
        """Validate a single zone for configuration errors that would silently
        corrupt waveform generation.

        Checks:
          - ``divisors`` is non-empty (empty list → silent silence output).
          - ``len(divisors) == len(amplitude_weights)`` (mismatch → zip()
            truncates silently, dropping the longer list's entries).
          - All divisors are > 0 (division-by-zero protection).
          - All amplitude_weights are in [0.0, 1.0].
          - Zone range is valid: range_min_m < range_max_m and both ≥ 0.

        Raises:
            ValueError: Describing the first misconfiguration found.
        """
        if len(zone.divisors) == 0:
            raise ValueError(
                f"Zone '{zone.name}': divisors list is empty — "
                "generate_stacked_waveform would return silence."
            )
        if len(zone.divisors) != len(zone.amplitude_weights):
            raise ValueError(
                f"Zone '{zone.name}': len(divisors)={len(zone.divisors)} != "
                f"len(amplitude_weights)={len(zone.amplitude_weights)} — "
                "zip() would silently truncate the shorter list."
            )
        for d in zone.divisors:
            if d <= 0:
                raise ValueError(
                    f"Zone '{zone.name}': divisor {d} ≤ 0 — "
                    "would cause division by zero in frequency computation."
                )
        for w in zone.amplitude_weights:
            if not (0.0 <= w <= 1.0):
                raise ValueError(
                    f"Zone '{zone.name}': amplitude_weight {w} is outside "
                    "[0.0, 1.0]."
                )
        if zone.range_min_m < 0:
            raise ValueError(
                f"Zone '{zone.name}': range_min_m={zone.range_min_m} < 0."
            )
        if zone.range_min_m >= zone.range_max_m:
            raise ValueError(
                f"Zone '{zone.name}': range_min_m={zone.range_min_m} >= "
                f"range_max_m={zone.range_max_m} — zone has zero or inverted range."
            )

    def get_zone(self, range_m: float) -> EngagementZone | None:
        """Return the engagement zone for a given target range.

        Returns None if the target is outside all zone boundaries.
        """
        for zone in self.zones:
            if zone.range_min_m <= range_m < zone.range_max_m:
                return zone
        return None

    def get_zone_frequencies(self, zone: EngagementZone,
                             radial_speed_ms: float = 0.0) -> list[float]:
        """Return the actual emission frequencies (Hz) for a zone's divisors.

        When ``radial_speed_ms`` is provided, every frequency is Doppler
        pre-compensated so the moving target receives the correct resonant
        subharmonic.  Each subharmonic is compensated independently because
        each has a different wavelength and therefore a different absolute
        Doppler shift.

        Args:
            zone: Engagement zone.
            radial_speed_ms: Target radial speed (m/s, + = approaching).
        """
        at_rest = [self.base_freq_hz / d for d in zone.divisors]
        if abs(radial_speed_ms) < 0.01:
            return at_rest
        return [doppler_precompensate(f, radial_speed_ms) for f in at_rest]

    def generate_stacked_waveform(self, zone: EngagementZone,
                                  duration_ms: int = 200,
                                  radial_speed_ms: float = 0.0) -> np.ndarray:
        """Generate a multi-tone waveform by superposition for a zone.

        Each subharmonic is a pure continuous tone at its designated
        frequency and amplitude weight.  In burst mode, the combined
        waveform is shaped into a pulse train.

        The tones are phase-coherent — all start at phase 0 — which
        maximizes constructive interference at intermodulation products.

        When ``radial_speed_ms`` is non-zero, each tone is Doppler
        pre-compensated so the moving target receives the intended
        resonant subharmonic.

        Args:
            zone: The engagement zone defining which frequencies to stack.
            duration_ms: Output duration in milliseconds.
            radial_speed_ms: Target radial speed (m/s, + = approaching).

        Returns:
            float32 numpy array of samples, values clipped to [-1, 1].
        """
        sr = self.sample_rate
        duration_s = duration_ms / 1000.0
        n_samples = int(sr * duration_s)

        if n_samples == 0:
            return np.array([], dtype=np.float32)

        # Guard: catch silent-failure misconfigurations before computing
        if len(zone.divisors) == 0:
            return np.zeros(n_samples, dtype=np.float32)
        if len(zone.divisors) != len(zone.amplitude_weights):
            raise ValueError(
                f"Zone '{zone.name}': len(divisors)={len(zone.divisors)} != "
                f"len(amplitude_weights)={len(zone.amplitude_weights)}"
            )

        t = np.linspace(0, duration_s, n_samples, endpoint=False,
                        dtype=np.float64)

        # Superpose all subharmonic tones (Doppler-compensated if moving)
        combined = np.zeros(n_samples, dtype=np.float64)
        freqs = self.get_zone_frequencies(zone, radial_speed_ms)

        for freq, weight in zip(freqs, zone.amplitude_weights):
            combined += weight * np.sin(2.0 * np.pi * freq * t)

        # Normalize to prevent clipping — scale so peak = max amplitude
        peak = np.max(np.abs(combined))
        if peak > 0:
            combined /= peak

        if zone.mode == "burst":
            combined = self._apply_burst_envelope(combined, zone, sr)

        return combined.astype(np.float32)

    def _apply_burst_envelope(self, waveform: np.ndarray,
                              zone: EngagementZone,
                              sample_rate: int) -> np.ndarray:
        """Shape a continuous multi-tone into a pulse train.

        Applies the same attack envelope and repetition structure as
        BurstConfig, but over the pre-mixed multi-tone waveform.
        """
        n_samples = len(waveform)
        pulse_samples = int(sample_rate * zone.pulse_ms / 1000.0)
        period_samples = int(sample_rate / zone.rep_rate_hz)

        if period_samples <= 0 or pulse_samples <= 0:
            return waveform

        # Build envelope: pulse-on + silence-off per period
        envelope = np.zeros(n_samples, dtype=np.float64)
        rise_samples = max(1, int(sample_rate * 0.08 / 1000.0))  # 0.08ms rise

        pos = 0
        while pos < n_samples:
            end = min(pos + pulse_samples, n_samples)
            burst_len = end - pos
            # Fill this burst window
            envelope[pos:end] = 1.0
            # Sharp exponential attack at the start of each burst
            actual_rise = min(rise_samples, burst_len)
            attack = 1.0 - np.exp(-5.0 * np.arange(actual_rise,
                                                     dtype=np.float64)
                                  / actual_rise)
            envelope[pos:pos + actual_rise] = attack
            pos += period_samples

        return waveform * envelope

    def get_status(self, range_m: float) -> dict:
        """Return status dict for telemetry reporting."""
        zone = self.get_zone(range_m)
        if zone is None:
            return {
                "ladder_active": False,
                "base_freq_hz": self.base_freq_hz,
                "zone": None,
                "frequencies_hz": [],
                "range_m": round(range_m, 1),
            }
        return {
            "ladder_active": True,
            "base_freq_hz": self.base_freq_hz,
            "zone": zone.name,
            "frequencies_hz": [round(f, 1)
                               for f in self.get_zone_frequencies(zone)],
            "amplitudes": zone.amplitude_weights,
            "mode": zone.mode,
            "range_m": round(range_m, 1),
        }
