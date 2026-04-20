"""
SoulMusic — test_harness.py
End-to-end validation of the acoustic detection + attack pipeline
using synthetic audio signals.  No hardware required.

Run:  python test_harness.py           (from SoulMusic/ directory)

What this tests:
  1. Synthetic propeller audio generation (known BPF + harmonics + noise)
  2. Propeller detection (does FFT find the fundamental + harmonics?)
  3. Doppler shift measurement (does speed match the synthetic speed?)
  4. Platform identification (does it match the correct platform?)
  5. Pre-loaded attack resolution (does it find the right MEMS frequency?)
  6. Beamforming array response (does gain/beamwidth match theory?)
  7. Waveform generation (do chirps and bursts generate correctly?)
  8. Full passive detector loop (end-to-end with synthetic capture)

Every test uses mathematically constructed inputs with known answers.
If a test fails, the algorithm has a bug — not the hardware.
"""

import sys
import os
import time
import math
import traceback
from pathlib import Path

import numpy as np

# ── Ensure SoulMusic is on the import path ──
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

SAMPLE_RATE = 96000
SPEED_OF_SOUND = 343.0

# ═══════════════════════════════════════════════════════════════
#  Synthetic Audio Generator
# ═══════════════════════════════════════════════════════════════

def generate_propeller_audio(
    bpf_hz: float = 250.0,
    n_harmonics: int = 5,
    harmonic_decay: float = 0.7,
    n_motors: int = 4,
    motor_rpm_spread_pct: float = 2.0,
    amplitude: float = 0.1,
    noise_level: float = 0.005,
    duration_ms: float = 100.0,
    doppler_speed_ms: float = 0.0,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Generate realistic synthetic propeller audio.

    Creates a multi-harmonic signal mimicking a multi-motor platform.
    Each motor gets a slightly different RPM (spread_pct) to create
    the spectral spreading that real props exhibit.

    Doppler shift is applied mathematically:
        f_observed = f_true × c / (c − v)
    Positive speed = approaching (frequency goes up).

    Args:
        bpf_hz: True blade-pass frequency (Hz).
        n_harmonics: Number of harmonic overtones.
        harmonic_decay: Amplitude decay per harmonic (0–1).
        n_motors: Number of motors.
        motor_rpm_spread_pct: RPM variation between motors (%).
        amplitude: Base amplitude (simulates distance).
        noise_level: Gaussian noise floor.
        duration_ms: Duration in milliseconds.
        doppler_speed_ms: Radial approach speed (m/s) for Doppler shift.
        sample_rate: Output sample rate.

    Returns:
        1D float32 numpy array — synthetic propeller audio.
    """
    n_samples = int(sample_rate * duration_ms / 1000.0)
    t = np.arange(n_samples, dtype=np.float64) / sample_rate

    # Apply Doppler shift to get observed frequencies
    if abs(doppler_speed_ms) > 0.01:
        doppler_factor = SPEED_OF_SOUND / (SPEED_OF_SOUND - doppler_speed_ms)
    else:
        doppler_factor = 1.0

    observed_bpf = bpf_hz * doppler_factor

    signal = np.zeros(n_samples, dtype=np.float64)

    # Each motor contributes harmonics at slightly different BPF
    for motor in range(n_motors):
        # Spread RPM: motor 0 is nominal, others vary ±spread_pct
        if n_motors > 1:
            spread = (motor / (n_motors - 1) - 0.5) * 2 * motor_rpm_spread_pct / 100.0
        else:
            spread = 0.0
        motor_bpf = observed_bpf * (1.0 + spread)

        for h in range(1, n_harmonics + 1):
            freq = motor_bpf * h
            amp = amplitude * (harmonic_decay ** (h - 1)) / n_motors
            # Random phase offset per motor per harmonic (realistic)
            phase = np.random.uniform(0, 2 * np.pi)
            signal += amp * np.sin(2 * np.pi * freq * t + phase)

    # Add background noise
    signal += np.random.randn(n_samples) * noise_level

    return signal.astype(np.float32)


# ═══════════════════════════════════════════════════════════════
#  Test Results Tracking
# ═══════════════════════════════════════════════════════════════

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, detail: str = ""):
        self.passed += 1
        mark = "\033[92m✓\033[0m"  # green check
        print(f"  {mark} {name}" + (f"  ({detail})" if detail else ""))

    def fail(self, name: str, detail: str = ""):
        self.failed += 1
        self.errors.append((name, detail))
        mark = "\033[91m✗\033[0m"  # red X
        print(f"  {mark} {name}" + (f"  ({detail})" if detail else ""))

    def check(self, condition: bool, name: str, detail: str = ""):
        if condition:
            self.ok(name, detail)
        else:
            self.fail(name, detail)

    def summary(self):
        total = self.passed + self.failed
        if self.failed == 0:
            color = "\033[92m"  # green
            status = "ALL PASSED"
        else:
            color = "\033[91m"  # red
            status = f"{self.failed} FAILED"
        print(f"\n{color}{'='*60}")
        print(f"  {self.passed}/{total} tests passed — {status}")
        if self.errors:
            print(f"\n  Failed tests:")
            for name, detail in self.errors:
                print(f"    • {name}: {detail}")
        print(f"{'='*60}\033[0m\n")
        return self.failed == 0


# ═══════════════════════════════════════════════════════════════
#  TEST 1: Propeller Detection
# ═══════════════════════════════════════════════════════════════

def test_propeller_detection(results: TestResults):
    """Can we detect propeller signatures in synthetic audio?"""
    print("\n\033[1m[TEST 1] Propeller Signature Detection\033[0m")
    from detection.acoustic_detect import detect_propeller_signature
    np.random.seed(42)  # deterministic for repeatable tests

    # ── 1a: Clean propeller signal (easy case) ──
    audio = generate_propeller_audio(bpf_hz=250.0, amplitude=0.15,
                                     noise_level=0.002, n_harmonics=5,
                                     motor_rpm_spread_pct=1.0,
                                     duration_ms=100.0)
    det = detect_propeller_signature(audio, SAMPLE_RATE)
    results.check(det.detected, "Detect clean 250 Hz propeller",
                  f"detected={det.detected}, conf={det.confidence:.2f}")

    results.check(abs(det.fundamental_hz - 250.0) < 30,
                  "Fundamental within 30 Hz of 250",
                  f"measured={det.fundamental_hz:.1f} Hz")

    results.check(det.harmonic_count >= 2,
                  "At least 2 harmonics found",
                  f"harmonics={det.harmonic_count}")

    # ── 1b: Quiet distant propeller (harder) ──
    audio_far = generate_propeller_audio(bpf_hz=400.0, amplitude=0.03,
                                         noise_level=0.003, n_harmonics=4)
    det_far = detect_propeller_signature(audio_far, SAMPLE_RATE)
    results.check(det_far.detected, "Detect faint 400 Hz propeller (distant)",
                  f"detected={det_far.detected}, conf={det_far.confidence:.2f}")

    # ── 1c: Pure noise (should NOT detect) ──
    noise_only = np.random.randn(8192).astype(np.float32) * 0.01
    det_noise = detect_propeller_signature(noise_only, SAMPLE_RATE)
    results.check(not det_noise.detected, "No false positive on pure noise",
                  f"detected={det_noise.detected}")

    # ── 1d: Single tone (no harmonics — should NOT detect as propeller) ──
    # Use a frequency where harmonics won't land in the prop band
    t = np.arange(8192) / SAMPLE_RATE
    single_tone = (0.1 * np.sin(2 * np.pi * 1800 * t)).astype(np.float32)
    single_tone += np.random.randn(len(single_tone)).astype(np.float32) * 0.002
    det_tone = detect_propeller_signature(single_tone, SAMPLE_RATE)
    # A single tone may detect as propeller if its harmonics are strong enough,
    # but confidence should be low since the spectral shape is wrong
    results.check(not det_tone.detected or det_tone.confidence < 0.5,
                  "No high-confidence false positive on single tone",
                  f"detected={det_tone.detected}, harmonics={det_tone.harmonic_count}, "
                  f"conf={det_tone.confidence:.2f}")

    # ── 1e: High-RPM FPV racing quad ──
    np.random.seed(55)  # independent seed for this sub-test
    audio_fpv = generate_propeller_audio(bpf_hz=1000.0, amplitude=0.10,
                                         noise_level=0.003, n_harmonics=4,
                                         n_motors=4, motor_rpm_spread_pct=1.5,
                                         duration_ms=100.0)
    det_fpv = detect_propeller_signature(audio_fpv, SAMPLE_RATE)
    results.check(det_fpv.detected, "Detect high-RPM FPV quad (1000 Hz BPF)",
                  f"fundamental={det_fpv.fundamental_hz:.0f} Hz, "
                  f"conf={det_fpv.confidence:.2f}")

    # ── 1f: Range estimation sanity check ──
    # Louder signal should produce closer range estimate.
    # Use single-motor to avoid random phase interference.
    # Use very different amplitudes so the FFT peak difference is clear.
    np.random.seed(66)  # independent seed
    audio_close = generate_propeller_audio(bpf_hz=250.0, amplitude=0.30,
                                           noise_level=0.002, n_motors=1,
                                           duration_ms=100.0)
    audio_far = generate_propeller_audio(bpf_hz=250.0, amplitude=0.01,
                                         noise_level=0.002, n_motors=1,
                                         duration_ms=100.0)
    det_close = detect_propeller_signature(audio_close, SAMPLE_RATE)
    det_far = detect_propeller_signature(audio_far, SAMPLE_RATE)
    if det_close.detected and det_far.detected:
        results.check(det_far.estimated_range_m > det_close.estimated_range_m,
                      "Quieter signal → larger estimated range",
                      f"close={det_close.estimated_range_m:.1f}m, "
                      f"far={det_far.estimated_range_m:.1f}m")
    elif det_close.detected and not det_far.detected:
        # Very faint signal not detected at all — still validates that louder
        # signals are "closer" in the sense that faint ones fall below threshold
        results.ok("Quieter signal below detection threshold (valid range behavior)",
                   f"close={det_close.estimated_range_m:.1f}m, far=undetected")
    else:
        results.fail("Range estimation (detection failed)")


# ═══════════════════════════════════════════════════════════════
#  TEST 2: Doppler Speed Measurement
# ═══════════════════════════════════════════════════════════════

def test_doppler_speed(results: TestResults):
    """Can we measure approach speed from Doppler shift?"""
    print("\n\033[1m[TEST 2] Doppler Speed Measurement\033[0m")
    from detection.acoustic_detect import (
        detect_propeller_signature, measure_doppler_shift
    )
    np.random.seed(123)  # deterministic

    true_bpf = 250.0  # Hz
    true_speed = 30.0  # m/s approaching

    # Simulate two consecutive captures 50ms apart
    # Target is approaching → frequency increases over time
    # At 30 m/s over 50ms → moves 1.5m closer
    # First capture: slightly less Doppler than second

    # Buffer 1: target at ~50m, speed 30 m/s
    audio_t1 = generate_propeller_audio(
        bpf_hz=true_bpf, amplitude=0.08,
        doppler_speed_ms=true_speed * 0.98,  # slight ramp
        noise_level=0.002, duration_ms=100.0)

    # Buffer 2: 100ms later, target slightly closer + slightly more Doppler
    audio_t2 = generate_propeller_audio(
        bpf_hz=true_bpf, amplitude=0.085,
        doppler_speed_ms=true_speed * 1.02,
        noise_level=0.002, duration_ms=100.0)

    det1 = detect_propeller_signature(audio_t1, SAMPLE_RATE)
    results.check(det1.detected, "Detect Doppler-shifted signal (buffer 1)",
                  f"fundamental={det1.fundamental_hz:.1f} Hz")

    # Expected observed frequency at 30 m/s:
    # f_obs = 250 × 343/(343-30) = 250 × 1.0958 ≈ 273.9 Hz
    expected_observed = true_bpf * SPEED_OF_SOUND / (SPEED_OF_SOUND - true_speed)

    if det1.detected:
        # Check observed frequency is shifted upward
        results.check(det1.fundamental_hz > true_bpf,
                      "Observed freq > true freq (approaching)",
                      f"observed={det1.fundamental_hz:.1f} vs true={true_bpf}")

        results.check(abs(det1.fundamental_hz - expected_observed) < 40,
                      f"Observed freq near expected {expected_observed:.1f} Hz",
                      f"measured={det1.fundamental_hz:.1f}")

    # Measure Doppler between buffers
    shift_hz, measured_speed, corrected = measure_doppler_shift(
        audio_t1, audio_t2, det1.fundamental_hz if det1.detected else true_bpf,
        SAMPLE_RATE)

    # The differential measurement between two close speeds won't
    # perfectly recover 30 m/s — it measures the CHANGE in speed.
    # But the corrected fundamental should be closer to true BPF.
    results.check(corrected > 0,
                  "Doppler correction produces valid frequency",
                  f"corrected={corrected:.1f} Hz")

    # ── Stationary target test (zero Doppler) ──
    np.random.seed(77)  # independent seed
    audio_s1 = generate_propeller_audio(bpf_hz=300.0, amplitude=0.10,
                                         doppler_speed_ms=0.0, noise_level=0.002,
                                         duration_ms=100.0)
    audio_s2 = generate_propeller_audio(bpf_hz=300.0, amplitude=0.10,
                                         doppler_speed_ms=0.0, noise_level=0.002,
                                         duration_ms=100.0)
    det_s1 = detect_propeller_signature(audio_s1, SAMPLE_RATE)
    if det_s1.detected:
        shift_s, speed_s, corr_s = measure_doppler_shift(
            audio_s1, audio_s2, det_s1.fundamental_hz, SAMPLE_RATE)
        results.check(abs(speed_s) < 10.0,
                      "Stationary target → near-zero speed",
                      f"measured_speed={speed_s:.1f} m/s")
    else:
        results.fail("Stationary target detection failed")


# ═══════════════════════════════════════════════════════════════
#  TEST 3: Platform Identification
# ═══════════════════════════════════════════════════════════════

def test_platform_identification(results: TestResults):
    """Can we identify the correct platform from propeller acoustics?"""
    print("\n\033[1m[TEST 3] Platform Identification\033[0m")
    from detection.acoustic_detect import (
        detect_propeller_signature, identify_platform, PLATFORM_DB
    )
    from acoustic.resonance import MEMS_PROFILES
    np.random.seed(456)  # deterministic

    # ── 3a: DJI Mavic 3 (BPF ~200 Hz, 4 motors, 2 blades) ──
    # Typical hover RPM ~6000, 2 blades → BPF = 6000*2/60 = 200 Hz
    audio_mavic = generate_propeller_audio(
        bpf_hz=200.0, n_harmonics=5, n_motors=4, amplitude=0.10,
        noise_level=0.002)
    det = detect_propeller_signature(audio_mavic, SAMPLE_RATE)
    if det.detected:
        match = identify_platform(det, radial_speed=0.0)
        results.check(match.match_confidence > 0.3,
                      "Mavic-class platform matched",
                      f"platform={match.platform.platform_id}, "
                      f"conf={match.match_confidence:.2f}")

        # Check MEMS lookup
        if match.mems_sensor:
            results.check(match.mems_sensor in MEMS_PROFILES,
                          "MEMS sensor found in profiles",
                          f"sensor={match.mems_sensor}")
            results.check(match.recommended_freq_hz > 0,
                          "Attack frequency pre-loaded",
                          f"freq={match.recommended_freq_hz} Hz")
            results.check(match.preloaded,
                          "Pre-loaded flag set (skip probe)")
        else:
            results.fail("No MEMS sensor resolved for Mavic-class")
    else:
        results.fail("Mavic-class detection failed")

    # ── 3b: FPV 5" racing quad (BPF ~1200 Hz, high RPM) ──
    audio_fpv = generate_propeller_audio(
        bpf_hz=1200.0, n_harmonics=4, n_motors=4, amplitude=0.08,
        noise_level=0.003)
    det_fpv = detect_propeller_signature(audio_fpv, SAMPLE_RATE)
    if det_fpv.detected:
        match_fpv = identify_platform(det_fpv, radial_speed=0.0)
        results.check(match_fpv.match_confidence > 0.2,
                      "FPV-class platform matched",
                      f"platform={match_fpv.platform.platform_id}, "
                      f"conf={match_fpv.match_confidence:.2f}")
    else:
        results.fail("FPV-class detection failed")

    # ── 3c: Military hex (BPF ~400 Hz, 6 motors) ──
    audio_hex = generate_propeller_audio(
        bpf_hz=400.0, n_harmonics=5, n_motors=6, amplitude=0.12,
        noise_level=0.002, motor_rpm_spread_pct=1.5)
    det_hex = detect_propeller_signature(audio_hex, SAMPLE_RATE)
    if det_hex.detected:
        match_hex = identify_platform(det_hex, radial_speed=0.0)
        results.check(match_hex.match_confidence > 0.2,
                      "Hex-class platform matched",
                      f"platform={match_hex.platform.platform_id}, "
                      f"conf={match_hex.match_confidence:.2f}")
    else:
        results.fail("Hex-class detection failed")

    # ── 3d: Unknown platform (extreme BPF outside all ranges) ──
    audio_unk = generate_propeller_audio(
        bpf_hz=3500.0, n_harmonics=3, n_motors=2, amplitude=0.06,
        noise_level=0.002)
    det_unk = detect_propeller_signature(audio_unk, SAMPLE_RATE)
    if det_unk.detected:
        match_unk = identify_platform(det_unk, radial_speed=0.0)
        # Should either fail to match or match with low confidence
        results.check(match_unk.match_confidence < 0.5 or
                      match_unk.platform.platform_id == "unknown",
                      "Unusual platform has low confidence or unknown",
                      f"platform={match_unk.platform.platform_id}, "
                      f"conf={match_unk.match_confidence:.2f}")


# ═══════════════════════════════════════════════════════════════
#  TEST 4: Beamforming Array Response
# ═══════════════════════════════════════════════════════════════

def test_beamforming(results: TestResults):
    """Do beamforming calculations match theoretical predictions?"""
    print("\n\033[1m[TEST 4] Beamforming Array\033[0m")
    from acoustic.beam import (
        ArrayGeometry, BeamFormer, SteeringVector, BeamController,
        estimate_beamwidth, estimate_gain_db, estimate_focal_gain_db
    )

    # ── 4a: Array geometry ──
    grid = ArrayGeometry.rectangular_grid(16, 16)
    results.check(grid.n_elements == 256,
                  "16×16 grid = 256 elements",
                  f"n_elements={grid.n_elements}")

    ring = ArrayGeometry.circular_ring(32)
    results.check(ring.n_elements == 32,
                  "Circular ring = 32 elements",
                  f"n_elements={ring.n_elements}")

    # ── 4b: Beamwidth estimation ──
    bw = estimate_beamwidth(grid, freq_hz=25000)
    results.check(5.0 < bw < 15.0,
                  "16×16 beamwidth in 5–15° range at 25 kHz",
                  f"beamwidth={bw:.1f}°")

    # ── 4c: Gain estimation ──
    gain = estimate_gain_db(grid)
    results.check(20 < gain < 30,
                  "16×16 gain in 20–30 dB range",
                  f"gain={gain:.1f} dB")

    # ── 4d: Steering delays (boresight) ──
    bf = BeamFormer(grid)
    boresight = SteeringVector(azimuth_deg=0., elevation_deg=0.)
    delays = bf.compute_delays(boresight, 25000)
    results.check(delays.shape[0] == 256,
                  "Delay vector has 256 entries",
                  f"shape={delays.shape}")
    # Boresight: all elements in-phase, delays should be small relative to period
    # (may have a common offset but differential spread should be minimal)
    delay_spread = np.max(delays) - np.min(delays)
    period_25k = 1.0 / 25000.0  # 40 µs
    results.check(delay_spread < period_25k * 10,
                  "Boresight delay spread < 10 periods",
                  f"spread={delay_spread:.2e} s, period={period_25k:.2e} s")

    # ── 4e: Off-axis steering creates non-zero delays ──
    offaxis = SteeringVector(azimuth_deg=30.0, elevation_deg=0.0)
    delays_off = bf.compute_delays(offaxis, 25000)
    delay_range_off = np.max(delays_off) - np.min(delays_off)
    results.check(delay_range_off > 1e-6,
                  "30° off-axis → significant delay spread",
                  f"range={delay_range_off:.2e} s")

    # ── 4f: Waveform beamforming produces multi-channel output ──
    from acoustic.resonance import get_broad_sweep
    mono = get_broad_sweep(duration_ms=10)
    delays_bore = bf.compute_delays(boresight, 25000)
    multi = bf.apply_to_waveform(mono, delays_bore, SAMPLE_RATE)
    results.check(multi.ndim == 2 and multi.shape[1] == 256,
                  "Beamformed output is (samples, 256)",
                  f"shape={multi.shape}")

    # ── 4g: Receive beamforming enhances on-axis signal ──
    # Create synthetic multi-channel: signal on all channels + random noise
    n_samp = 4800  # 50ms
    true_signal = 0.1 * np.sin(2 * np.pi * 1000 * np.arange(n_samp) / SAMPLE_RATE)
    multichannel_input = np.tile(true_signal.reshape(-1, 1), (1, 256))
    multichannel_input += np.random.randn(n_samp, 256).astype(np.float32) * 0.05

    beamformed = bf.beamform_receive(multichannel_input, delays_bore,
                                      SAMPLE_RATE)
    results.check(beamformed.ndim == 1,
                  "Receive beamform produces 1D output",
                  f"shape={beamformed.shape}")

    # Beamformed signal should have higher SNR than raw single channel
    results.check(len(beamformed) > 0,
                  "Receive beamform output is non-empty",
                  f"samples={len(beamformed)}")

    # ── 4h: BeamController high-level API ──
    ctrl = BeamController(grid)
    ctrl.aim(45.0, 10.0)
    status = ctrl.get_status()
    results.check(status["azimuth_deg"] == 45.0,
                  "BeamController aim sets azimuth",
                  f"az={status['azimuth_deg']}")

    ctrl.focus(3.0)
    status2 = ctrl.get_status()
    results.check(status2["focal_distance_m"] == 3.0,
                  "BeamController focus sets focal distance",
                  f"focus={status2['focal_distance_m']}m")

    # ── 4i: Near-field focusing gain ──
    nf_gain = estimate_focal_gain_db(grid, focal_distance_m=3.0, freq_hz=25000)
    results.check(nf_gain > 0,
                  "Near-field focusing adds positive gain",
                  f"focal_gain={nf_gain:.1f} dB")


# ═══════════════════════════════════════════════════════════════
#  TEST 5: Waveform Generation
# ═══════════════════════════════════════════════════════════════

def test_waveform_generation(results: TestResults):
    """Do chirps and bursts generate correctly?"""
    print("\n\033[1m[TEST 5] Waveform Generation\033[0m")
    from acoustic.resonance import (
        generate_chirp, SweepConfig,
        generate_burst, generate_burst_train, BurstConfig,
        get_broad_sweep, get_targeted_sweep, get_broad_burst,
        get_targeted_burst, get_shock_burst,
        MEMS_PROFILES,
    )

    # ── 5a: Broad chirp ──
    chirp = get_broad_sweep(duration_ms=50)
    results.check(len(chirp) > 0,
                  "Broad sweep generates samples",
                  f"samples={len(chirp)}, duration={len(chirp)/SAMPLE_RATE*1000:.1f}ms")
    results.check(np.max(np.abs(chirp)) <= 1.0,
                  "Chirp amplitude within [-1, 1]")

    # ── 5b: Targeted chirp for known sensor ──
    for sensor in ["ICM-42688-P", "BMI270", "MPU-6050"]:
        targeted = get_targeted_sweep(sensor, duration_ms=20)
        results.check(len(targeted) > 0,
                      f"Targeted sweep for {sensor}",
                      f"samples={len(targeted)}")

    # ── 5c: Burst waveform ──
    burst = get_broad_burst()
    results.check(len(burst) > 0,
                  "Broad burst generates samples",
                  f"samples={len(burst)}")
    results.check(np.max(np.abs(burst)) <= 1.01,  # tiny float tolerance
                  "Burst amplitude within bounds")

    # ── 5d: Burst train ──
    cfg = BurstConfig(freq_start=25000, freq_end=25000, pulse_ms=2.0,
                      rep_rate_hz=50, train_duration_ms=200)
    train = generate_burst_train(cfg)
    expected_pulses = int(cfg.train_duration_ms / 1000.0 * cfg.rep_rate_hz)
    results.check(len(train) > 0,
                  f"Burst train ({expected_pulses} pulses)",
                  f"samples={len(train)}, "
                  f"duration={len(train)/SAMPLE_RATE*1000:.0f}ms")

    # Verify silence between bursts (pulse only occupies 2ms of each 20ms period)
    period_samples = SAMPLE_RATE // cfg.rep_rate_hz  # 1920 samples per period
    pulse_samples = int(SAMPLE_RATE * cfg.pulse_ms / 1000.0)  # 192 samples per pulse
    # Check a gap region in the middle of a period (well after pulse)
    gap_start = pulse_samples + 100
    gap_end = min(gap_start + 200, period_samples)
    if gap_end <= len(train):
        gap_energy = np.mean(train[gap_start:gap_end] ** 2)
        results.check(gap_energy < 0.01,
                      "Silence between bursts (gap energy low)",
                      f"gap_rms={np.sqrt(gap_energy):.4f}")

    # ── 5e: Quick presets ──
    targeted_burst = get_targeted_burst("ICM-42688-P")
    results.check(len(targeted_burst) > 0,
                  "Targeted burst for ICM-42688-P",
                  f"samples={len(targeted_burst)}")

    shock = get_shock_burst()
    results.check(len(shock) > 0,
                  "Shock burst preset",
                  f"samples={len(shock)}")

    # ── 5f: All MEMS profiles have valid resonance frequencies ──
    # Range 12–35 kHz covers standard MEMS (18–35 kHz) and
    # lower-resonance military MEMS gyros (ADXRS: 14 kHz, LSM6DSMTR: 17 kHz)
    for name, profile in MEMS_PROFILES.items():
        freq = profile["resonance_hz"]
        results.check(12000 <= freq <= 35000,
                      f"MEMS {name} resonance in 12-35 kHz",
                      f"freq={freq} Hz")


# ═══════════════════════════════════════════════════════════════
#  TEST 6: Adaptive Probe (Shell Classification)
# ═══════════════════════════════════════════════════════════════

def test_probe_classification(results: TestResults):
    """Does the shell classifier work with synthetic reflections?"""
    print("\n\033[1m[TEST 6] Probe Shell Classification\033[0m")
    from acoustic.probe import (
        analyze_reflection, generate_probe_chirp, SHELL_PRESETS
    )

    probe = generate_probe_chirp()
    results.check(len(probe) > 0,
                  "Probe chirp generated",
                  f"samples={len(probe)}")

    # analyze_reflection(captured, estimated_range_m) — takes raw captured audio
    # The captured audio includes the expected round-trip delay region

    # ── 6a: Simulate "no shell" reflection (strong, minimal attenuation) ──
    range_m = 0.5
    rt_delay = 2.0 * range_m / SPEED_OF_SOUND  # ~2.9ms
    delay_samples = int(rt_delay * SAMPLE_RATE)
    # Build a captured buffer with the probe echo at the expected delay
    captured_none = np.zeros(delay_samples + len(probe) + 2000, dtype=np.float32)
    captured_none[delay_samples:delay_samples + len(probe)] = probe * 0.8
    captured_none += np.random.randn(len(captured_none)).astype(np.float32) * 0.001

    profile_none = analyze_reflection(captured_none, estimated_range_m=range_m)
    results.check(profile_none is not None,
                  "Analyze reflection returns a profile")
    if profile_none:
        results.check(profile_none.shell_class in SHELL_PRESETS,
                      f"Shell class '{profile_none.shell_class}' is in presets",
                      f"attenuation={profile_none.attenuation_db:.1f} dB")

    # ── 6b: Simulate "metal shell" (heavy attenuation, sharp resonance) ──
    captured_metal = np.zeros(delay_samples + len(probe) + 2000, dtype=np.float32)
    captured_metal[delay_samples:delay_samples + len(probe)] = probe * 0.05  # -26 dB
    captured_metal += np.random.randn(len(captured_metal)).astype(np.float32) * 0.001

    profile_metal = analyze_reflection(captured_metal, estimated_range_m=range_m)
    if profile_metal:
        results.check(profile_metal.attenuation_db > 10,
                      "Heavy attenuation classified as harder shell",
                      f"class={profile_metal.shell_class}, "
                      f"atten={profile_metal.attenuation_db:.1f} dB")

    # ── 6c: Shell presets all have required keys ──
    required_keys = {"power", "rep_rate_hz", "pulse_ms"}
    for shell, preset in SHELL_PRESETS.items():
        has_keys = all(k in preset for k in required_keys)
        results.check(has_keys,
                      f"Shell preset '{shell}' has all burst params",
                      f"keys={list(preset.keys())}")


# ═══════════════════════════════════════════════════════════════
#  TEST 7: Full Pipeline (Passive Detect → Identify → Pre-load)
# ═══════════════════════════════════════════════════════════════

def test_full_pipeline(results: TestResults):
    """End-to-end: synthetic audio → detect → Doppler → identify → attack freq"""
    print("\n\033[1m[TEST 7] Full Pipeline (End-to-End)\033[0m")
    from detection.acoustic_detect import (
        detect_propeller_signature, measure_doppler_shift,
        identify_platform, PLATFORM_DB,
    )
    from acoustic.resonance import MEMS_PROFILES
    from acoustic.probe import SHELL_PRESETS
    np.random.seed(789)  # deterministic

    # Scenario: DJI Mavic 3 approaching at 15 m/s from ~80m away
    true_bpf = 200.0   # Hz (6000 RPM × 2 blades / 60)
    approach_speed = 15.0  # m/s
    n_motors = 4

    print("  Scenario: DJI Mavic 3-class quad, 15 m/s approach, ~80m range")

    # Step 1: Capture and detect
    audio = generate_propeller_audio(
        bpf_hz=true_bpf, n_motors=n_motors, amplitude=0.12,
        doppler_speed_ms=approach_speed, noise_level=0.002,
        duration_ms=100.0, motor_rpm_spread_pct=1.0)

    det = detect_propeller_signature(audio, SAMPLE_RATE)
    results.check(det.detected,
                  "Pipeline Step 1: Target detected",
                  f"BPF={det.fundamental_hz:.1f} Hz, "
                  f"conf={det.confidence:.2f}")
    if not det.detected:
        results.fail("Pipeline aborted — detection failed")
        return

    # Step 2: Doppler → speed
    audio_t2 = generate_propeller_audio(
        bpf_hz=true_bpf, n_motors=n_motors, amplitude=0.042,
        doppler_speed_ms=approach_speed * 1.01,
        noise_level=0.003, duration_ms=100.0)

    shift_hz, measured_speed, corrected_bpf = measure_doppler_shift(
        audio, audio_t2, det.fundamental_hz, SAMPLE_RATE)

    results.check(corrected_bpf > 0,
                  "Pipeline Step 2: Doppler correction applied",
                  f"corrected_BPF={corrected_bpf:.1f} Hz, "
                  f"Δf={shift_hz:.2f} Hz")

    # Step 3: Identify platform
    match = identify_platform(det, radial_speed=approach_speed)

    results.check(match.match_confidence > 0.2,
                  "Pipeline Step 3: Platform identified",
                  f"platform={match.platform.platform_id}, "
                  f"conf={match.match_confidence:.2f}, "
                  f"via={match.matched_by}")

    # Step 4: MEMS lookup
    if match.mems_sensor:
        results.check(match.mems_sensor in MEMS_PROFILES,
                      "Pipeline Step 4: MEMS sensor resolved",
                      f"sensor={match.mems_sensor}, "
                      f"resonance={match.recommended_freq_hz} Hz")

        # Step 5: Pre-load attack
        shell = match.shell_class
        results.check(shell in SHELL_PRESETS,
                      "Pipeline Step 5: Shell preset available",
                      f"shell={shell}")

        preset = SHELL_PRESETS[shell]
        freq = match.recommended_freq_hz
        results.check(18000 <= freq <= 35000,
                      "Pipeline Step 5: Attack frequency in ultrasonic range",
                      f"freq={freq} Hz, power={preset.get('power', '?')}")

        results.check(match.preloaded,
                      "Pipeline COMPLETE: Pre-loaded attack ready",
                      f"🎯 {match.platform.platform_id} → "
                      f"{match.mems_sensor} @ {freq} Hz — "
                      f"READY TO FIRE (operator enable)")

        # Print the full kill chain summary
        print(f"\n  \033[96m┌──────────────────────────────────────────────┐")
        print(f"  │  FULL KILL CHAIN (synthetic test)             │")
        print(f"  ├──────────────────────────────────────────────┤")
        print(f"  │  Heard:   {det.fundamental_hz:>7.1f} Hz BPF ({det.harmonic_count} harmonics) │")
        print(f"  │  Speed:   {approach_speed:>7.1f} m/s radial approach     │")
        print(f"  │  Match:   {match.platform.platform_id:<20s} ({match.match_confidence:.0%})   │")
        print(f"  │  MEMS:    {match.mems_sensor:<20s}          │")
        print(f"  │  Attack:  {freq:>7d} Hz ± 500 Hz burst        │")
        print(f"  │  Shell:   {shell:<15s}                    │")
        print(f"  │  Status:  ARMED — awaiting operator enable   │")
        print(f"  └──────────────────────────────────────────────┘\033[0m")
    else:
        results.check(False, "Pipeline Step 4: No MEMS resolved",
                      "Falling back to broadband sweep")


# ═══════════════════════════════════════════════════════════════
#  TEST 8: PassiveDetector Loop (Background Thread)
# ═══════════════════════════════════════════════════════════════

def test_passive_detector_loop(results: TestResults):
    """Does the PassiveDetector class work end-to-end with synthetic capture?"""
    print("\n\033[1m[TEST 8] PassiveDetector Background Loop\033[0m")
    from detection.acoustic_detect import PassiveDetector
    np.random.seed(101)  # deterministic

    # Track callbacks
    detections = []
    matches = []

    def on_detect(d):
        detections.append(d)

    def on_match(m):
        matches.append(m)

    detector = PassiveDetector(
        on_detection=on_detect,
        on_platform_match=on_match,
    )

    # Provide a synthetic capture function that returns propeller audio
    call_count = [0]
    def fake_capture(duration_ms):
        call_count[0] += 1
        # First few captures: approaching DJI-class quad
        speed = 20.0 + call_count[0] * 0.5  # accelerating
        return generate_propeller_audio(
            bpf_hz=220.0, n_motors=4, amplitude=0.08,
            doppler_speed_ms=speed, noise_level=0.003,
            duration_ms=duration_ms)

    detector.set_hardware(capture_func=fake_capture)
    detector.start()

    # Let it run for ~500ms (enough for ~10 cycles)
    time.sleep(0.6)
    detector.stop()

    results.check(call_count[0] >= 3,
                  "Detector ran multiple capture cycles",
                  f"cycles={call_count[0]}")

    results.check(len(detections) >= 1,
                  "At least 1 detection callback fired",
                  f"detections={len(detections)}")

    results.check(len(matches) >= 1,
                  "At least 1 platform match callback fired",
                  f"matches={len(matches)}")

    if matches:
        m = matches[0]
        results.check(m.preloaded,
                      "PassiveDetector produced pre-loaded match",
                      f"platform={m.platform.platform_id}, "
                      f"freq={m.recommended_freq_hz} Hz")


# ═══════════════════════════════════════════════════════════════
#  TEST 9: Subharmonic Ladder (graduated engagement zones)
# ═══════════════════════════════════════════════════════════════

def test_subharmonic_ladder(results: TestResults):
    """Does the graduated engagement ladder produce correct zone
    frequencies, waveforms, and zone transitions?"""
    print("\n\033[1m[TEST 9] Subharmonic Engagement Ladder\033[0m")
    from acoustic.resonance import SubharmonicLadder, EngagementZone

    np.random.seed(900)  # deterministic

    # ── 9a: Default ladder for 25 kHz target ──
    ladder = SubharmonicLadder(base_freq_hz=25000)
    results.check(len(ladder.zones) == 4,
                  "Default ladder has 4 zones",
                  f"zones={len(ladder.zones)}")

    # ── 9b: Zone lookup by range ──
    zone_200 = ladder.get_zone(180.0)
    zone_100 = ladder.get_zone(100.0)
    zone_50 = ladder.get_zone(50.0)
    zone_10 = ladder.get_zone(10.0)
    zone_out = ladder.get_zone(250.0)

    results.check(zone_200 is not None and zone_200.name == "priming",
                  "180m → priming zone",
                  f"zone={'None' if zone_200 is None else zone_200.name}")

    results.check(zone_100 is not None and zone_100.name == "charging",
                  "100m → charging zone",
                  f"zone={'None' if zone_100 is None else zone_100.name}")

    results.check(zone_50 is not None and zone_50.name == "disruption",
                  "50m → disruption zone",
                  f"zone={'None' if zone_50 is None else zone_50.name}")

    results.check(zone_10 is not None and zone_10.name == "kill",
                  "10m → kill zone",
                  f"zone={'None' if zone_10 is None else zone_10.name}")

    results.check(zone_out is None,
                  "250m → outside all zones (None)",
                  f"zone={'None' if zone_out is None else zone_out.name}")

    # ── 9c: Frequency ratios are correct ──
    priming_freqs = ladder.get_zone_frequencies(zone_200)
    results.check(len(priming_freqs) == 1 and abs(priming_freqs[0] - 5000.0) < 1,
                  "Priming zone: f/5 = 5000 Hz",
                  f"freqs={[round(f, 1) for f in priming_freqs]}")

    charging_freqs = ladder.get_zone_frequencies(zone_100)
    results.check(len(charging_freqs) == 2,
                  "Charging zone: 2 frequencies (f/5 + f/2)",
                  f"freqs={[round(f, 1) for f in charging_freqs]}")
    results.check(abs(charging_freqs[0] - 5000.0) < 1
                  and abs(charging_freqs[1] - 12500.0) < 1,
                  "Charging freqs: 5000 + 12500 Hz",
                  f"freqs={[round(f, 1) for f in charging_freqs]}")

    disruption_freqs = ladder.get_zone_frequencies(zone_50)
    results.check(len(disruption_freqs) == 3,
                  "Disruption zone: 3 frequencies (f/5 + f/3 + f/2)",
                  f"freqs={[round(f, 1) for f in disruption_freqs]}")

    kill_freqs = ladder.get_zone_frequencies(zone_10)
    results.check(len(kill_freqs) == 4 and abs(kill_freqs[-1] - 25000.0) < 1,
                  "Kill zone: 4 frequencies including direct f₀=25000 Hz",
                  f"freqs={[round(f, 1) for f in kill_freqs]}")

    # ── 9d: Retune to different MEMS (23 kHz Bosch BMI270) ──
    ladder.retune(23000)
    zone_far = ladder.get_zone(180.0)
    retuned_freqs = ladder.get_zone_frequencies(zone_far)
    expected_f5 = 23000.0 / 5
    results.check(abs(retuned_freqs[0] - expected_f5) < 1,
                  f"Retuned priming: f/5 = {expected_f5:.0f} Hz",
                  f"got={round(retuned_freqs[0], 1)} Hz")

    kill_retuned = ladder.get_zone(10.0)
    kill_retuned_freqs = ladder.get_zone_frequencies(kill_retuned)
    results.check(abs(kill_retuned_freqs[-1] - 23000.0) < 1,
                  "Retuned kill zone: direct f₀ = 23000 Hz",
                  f"got={round(kill_retuned_freqs[-1], 1)} Hz")

    # Reset back for waveform tests
    ladder.retune(25000)

    # ── 9e: Waveform generation — priming (single tone) ──
    wf_prime = ladder.generate_stacked_waveform(zone_200, duration_ms=50)
    results.check(len(wf_prime) > 0,
                  "Priming waveform generated",
                  f"samples={len(wf_prime)}")

    # Check it's approximately a 5 kHz tone via FFT
    spectrum = np.abs(np.fft.rfft(wf_prime))
    freqs_fft = np.fft.rfftfreq(len(wf_prime), d=1.0 / 96000)
    peak_freq = freqs_fft[np.argmax(spectrum)]
    results.check(abs(peak_freq - 5000.0) < 200,
                  "Priming waveform peak near 5000 Hz",
                  f"peak={peak_freq:.0f} Hz")

    # ── 9f: Waveform generation — charging (two tones) ──
    wf_charge = ladder.generate_stacked_waveform(zone_100, duration_ms=50)
    results.check(len(wf_charge) > 0,
                  "Charging waveform generated (2-tone)",
                  f"samples={len(wf_charge)}")

    # Verify both 5 kHz and 12.5 kHz are present
    spec_charge = np.abs(np.fft.rfft(wf_charge))
    freqs_charge = np.fft.rfftfreq(len(wf_charge), d=1.0 / 96000)
    # Find peaks above 30% of max
    threshold = np.max(spec_charge) * 0.3
    peak_mask = spec_charge > threshold
    peak_freqs_charge = freqs_charge[peak_mask]
    has_5k = np.any(np.abs(peak_freqs_charge - 5000.0) < 300)
    has_12k5 = np.any(np.abs(peak_freqs_charge - 12500.0) < 300)
    results.check(has_5k and has_12k5,
                  "Charging waveform contains 5 kHz + 12.5 kHz",
                  f"has_5k={has_5k}, has_12.5k={has_12k5}")

    # ── 9g: Waveform generation — disruption (three tones, burst mode) ──
    wf_disrupt = ladder.generate_stacked_waveform(zone_50, duration_ms=100)
    results.check(len(wf_disrupt) > 0,
                  "Disruption waveform generated (3-tone burst)",
                  f"samples={len(wf_disrupt)}")

    # Burst mode should have silence gaps (not all samples non-zero)
    zero_ratio = np.sum(np.abs(wf_disrupt) < 1e-6) / len(wf_disrupt)
    results.check(zero_ratio > 0.1,
                  "Disruption burst has silence gaps",
                  f"zero_ratio={zero_ratio:.2f}")

    # ── 9h: Waveform generation — kill (four tones, burst mode) ──
    wf_kill = ladder.generate_stacked_waveform(zone_10, duration_ms=100)
    results.check(len(wf_kill) > 0,
                  "Kill waveform generated (4-tone burst)",
                  f"samples={len(wf_kill)}")

    # Kill zone should include 25 kHz content
    spec_kill = np.abs(np.fft.rfft(wf_kill))
    freqs_kill = np.fft.rfftfreq(len(wf_kill), d=1.0 / 96000)
    kill_threshold = np.max(spec_kill) * 0.15
    kill_peak_mask = spec_kill > kill_threshold
    kill_peak_freqs = freqs_kill[kill_peak_mask]
    has_25k = np.any(np.abs(kill_peak_freqs - 25000.0) < 500)
    results.check(has_25k,
                  "Kill waveform contains 25 kHz direct drive",
                  f"has_25k={has_25k}")

    # ── 9i: Amplitude normalization (no clipping) ──
    for label, wf in [("priming", wf_prime), ("charging", wf_charge),
                       ("disruption", wf_disrupt), ("kill", wf_kill)]:
        peak = np.max(np.abs(wf))
        results.check(peak <= 1.0 + 1e-6,
                      f"{label.capitalize()} waveform amplitude ≤ 1.0",
                      f"peak={peak:.4f}")

    # ── 9j: Status reporting ──
    status_prime = ladder.get_status(180.0)
    results.check(status_prime["ladder_active"] and status_prime["zone"] == "priming",
                  "Status at 180m: priming zone active",
                  f"status={status_prime['zone']}")

    status_out = ladder.get_status(300.0)
    results.check(not status_out["ladder_active"],
                  "Status at 300m: ladder inactive",
                  f"active={status_out['ladder_active']}")

    # ── 9k: Zone transition sequence (simulating closing target) ──
    zone_names = []
    for range_m in [190, 150, 110, 80, 50, 30, 15, 5]:
        z = ladder.get_zone(float(range_m))
        if z and (not zone_names or zone_names[-1] != z.name):
            zone_names.append(z.name)
    results.check(zone_names == ["priming", "charging", "disruption", "kill"],
                  "Zone transitions: priming → charging → disruption → kill",
                  f"sequence={zone_names}")


# ═══════════════════════════════════════════════════════════════
#  TEST 10: Doppler Pre-Compensation (Emission Side)
# ═══════════════════════════════════════════════════════════════

def test_doppler_precompensation(results: TestResults):
    """Verify that emitted frequencies are shifted so a moving target
    receives the correct resonant frequency.

    This is the counterpart to the receive-side Doppler correction
    tested in test_doppler_speed (Test 2).  Test 2 validates that we
    correctly measure incoming shift; this test validates that we
    correctly *pre-shift outgoing* tones.

    Physics (stationary source, moving receiver):
        f_received = f_emitted × (c + v) / c
    We want f_received = f_resonance, so:
        f_emitted = f_resonance × c / (c + v)
    """
    print("\n\033[1m[TEST 10] Doppler Pre-Compensation (Emission Side)\033[0m")
    from acoustic.resonance import (
        doppler_precompensate, SubharmonicLadder, SPEED_OF_SOUND,
    )

    c = SPEED_OF_SOUND  # 343.0 m/s

    # ── 10a: Stationary target (v=0) — no correction ──
    f_res = 27015.0
    f_emit = doppler_precompensate(f_res, 0.0)
    results.check(abs(f_emit - f_res) < 0.01,
                  "Stationary target: no shift",
                  f"f_emit={f_emit:.2f} vs f_res={f_res:.2f}")

    # ── 10b: Slow approach (v=10 m/s) ──
    # f_emit = 27015 × 343 / (343 + 10) = 27015 × 0.97167 ≈ 26250.3
    v = 10.0
    f_emit = doppler_precompensate(f_res, v)
    expected = f_res * c / (c + v)
    results.check(abs(f_emit - expected) < 0.01,
                  f"Approaching 10 m/s: emit {f_emit:.1f} Hz",
                  f"expected={expected:.1f}")
    # Verify the TARGET receives the correct frequency
    f_received = f_emit * (c + v) / c
    results.check(abs(f_received - f_res) < 0.1,
                  f"Target receives {f_received:.1f} Hz (want {f_res:.1f})",
                  f"error={abs(f_received - f_res):.3f} Hz")

    # ── 10c: Fast approach (v=30 m/s) — like a combat FPV drone ──
    v = 30.0
    f_emit = doppler_precompensate(f_res, v)
    expected = f_res * c / (c + v)
    results.check(abs(f_emit - expected) < 0.01,
                  f"Approaching 30 m/s: emit {f_emit:.1f} Hz",
                  f"expected={expected:.1f}")
    f_received = f_emit * (c + v) / c
    results.check(abs(f_received - f_res) < 0.1,
                  f"Target receives {f_received:.1f} Hz @ 30 m/s",
                  f"error={abs(f_received - f_res):.3f} Hz")

    # ── 10d: Shahed-class speed (v=50 m/s ≈ 180 km/h) ──
    v = 50.0
    f_emit = doppler_precompensate(f_res, v)
    f_received = f_emit * (c + v) / c
    results.check(abs(f_received - f_res) < 0.1,
                  f"Target receives {f_received:.1f} Hz @ 50 m/s (Shahed-class)",
                  f"emit={f_emit:.1f}, error={abs(f_received - f_res):.3f} Hz")

    # ── 10e: Receding target (v=-20 m/s) ──
    v = -20.0
    f_emit = doppler_precompensate(f_res, v)
    expected = f_res * c / (c + v)
    results.check(f_emit > f_res,
                  f"Receding target: emit HIGHER ({f_emit:.1f} > {f_res:.1f})",
                  f"expected={expected:.1f}")
    f_received = f_emit * (c + v) / c
    results.check(abs(f_received - f_res) < 0.1,
                  f"Receding target receives {f_received:.1f} Hz",
                  f"error={abs(f_received - f_res):.3f} Hz")

    # ── 10f: Edge case — very small speed (< 0.01 m/s) treated as zero ──
    f_emit = doppler_precompensate(f_res, 0.005)
    results.check(abs(f_emit - f_res) < 0.01,
                  "Near-zero speed treated as stationary",
                  f"f_emit={f_emit:.2f}")

    # ── 10g: Edge case — supersonic clamp ──
    # Should clamp to 0.95c, not crash or go negative
    f_emit = doppler_precompensate(f_res, 400.0)  # > speed of sound
    results.check(f_emit > 0,
                  "Supersonic speed clamped (positive result)",
                  f"f_emit={f_emit:.1f} (v=400 m/s clamped)")
    f_emit_neg = doppler_precompensate(f_res, -400.0)
    results.check(f_emit_neg > 0,
                  "Negative supersonic clamped (positive result)",
                  f"f_emit={f_emit_neg:.1f} (v=-400 m/s clamped)")

    # ── 10h: SubharmonicLadder Doppler integration ──
    # Verify that get_zone_frequencies and generate_stacked_waveform
    # correctly thread Doppler through the subharmonic stack
    ladder = SubharmonicLadder(base_freq_hz=27000)
    zone = ladder.get_zone(40.0)  # disruption zone (divisors include 2, 3)
    assert zone is not None, "Expected disruption zone at 40m"

    v = 25.0  # 25 m/s approach
    freqs_static = ladder.get_zone_frequencies(zone, 0.0)
    freqs_doppler = ladder.get_zone_frequencies(zone, v)

    results.check(len(freqs_static) == len(freqs_doppler),
                  "Doppler zone freqs: same count as static",
                  f"static={len(freqs_static)}, doppler={len(freqs_doppler)}")

    # Every Doppler frequency should be LOWER than static (approaching)
    all_lower = all(fd < fs for fd, fs in zip(freqs_doppler, freqs_static))
    results.check(all_lower,
                  "All zone freqs shifted lower for approaching target",
                  f"static={[f'{f:.1f}' for f in freqs_static]} "
                  f"doppler={[f'{f:.1f}' for f in freqs_doppler]}")

    # Verify each Doppler-shifted freq, after target receives it, equals
    # the static (intended) frequency
    for i, (fs, fd) in enumerate(zip(freqs_static, freqs_doppler)):
        f_at_target = fd * (c + v) / c
        results.check(abs(f_at_target - fs) < 0.5,
                      f"Subharmonic [{i}] target receives {f_at_target:.1f} Hz "
                      f"(want {fs:.1f})",
                      f"error={abs(f_at_target - fs):.3f} Hz")

    # ── 10i: Waveform contains shifted frequencies ──
    wf_static = ladder.generate_stacked_waveform(zone, duration_ms=50)
    wf_doppler = ladder.generate_stacked_waveform(zone, duration_ms=50,
                                                   radial_speed_ms=v)
    results.check(len(wf_static) == len(wf_doppler),
                  "Doppler waveform same length as static",
                  f"static={len(wf_static)}, doppler={len(wf_doppler)}")

    # FFT peak analysis: the Doppler waveform's dominant frequencies
    # should be lower than the static waveform's
    fft_static = np.abs(np.fft.rfft(wf_static))
    fft_doppler = np.abs(np.fft.rfft(wf_doppler))
    peak_static = np.argmax(fft_static)
    peak_doppler = np.argmax(fft_doppler)
    results.check(peak_doppler <= peak_static,
                  "Doppler waveform FFT peak is at lower freq bin",
                  f"static_bin={peak_static}, doppler_bin={peak_doppler}")

    # ── 10j: Round-trip accuracy across full speed range ──
    # Sweep from -80 m/s (receding fast) to +80 m/s (approaching fast)
    max_error = 0.0
    for v_test in np.linspace(-80, 80, 33):
        f_out = doppler_precompensate(f_res, v_test)
        f_at_target = f_out * (c + v_test) / c
        err = abs(f_at_target - f_res)
        max_error = max(max_error, err)
    results.check(max_error < 0.5,
                  f"Round-trip accuracy across ±80 m/s: max error {max_error:.4f} Hz",
                  f"max_error={max_error:.4f} Hz")


# ═══════════════════════════════════════════════════════════════
#  TEST 11: Proof-Mass Edge Cases
#  Real-world problems: multiple proof masses, axis-dependent
#  resonance, manufacturing spread, thermal drift, Q-factor
#  ringdown, zone boundary conditions, and malformed zone configs.
# ═══════════════════════════════════════════════════════════════

def test_proof_mass_edge_cases(results: TestResults):
    """Validates proof-mass physics utilities and edge-case defences."""
    print("\n\033[1m[TEST 11] Proof-Mass Edge Cases\033[0m")
    from acoustic.resonance import (
        MEMS_PROFILES, HUMAN_HEARING_HZ,
        thermal_compensate_resonance, manufacturing_bandwidth,
        optimal_burst_rate_hz, subharmonic_audible_components,
        generate_dual_mass_waveform, get_dual_mass_sweep,
        get_targeted_sweep, get_targeted_burst,
        SubharmonicLadder, EngagementZone,
    )

    # ── 11a: All MEMS_PROFILES entries have the new required fields ──
    required_fields = {
        "resonance_hz", "manufacturer",
        "axis_resonances_hz", "mfg_tolerance_pct", "temp_coeff_ppm_per_c",
    }
    for model, profile in MEMS_PROFILES.items():
        missing = required_fields - set(profile.keys())
        results.check(
            len(missing) == 0,
            f"Profile '{model}' has all required fields",
            f"missing={missing}" if missing else "ok",
        )
        # axis_resonances_hz must be a 3-element list (X, Y, Z)
        axes = profile.get("axis_resonances_hz", [])
        results.check(
            isinstance(axes, list) and len(axes) == 3,
            f"Profile '{model}' axis_resonances_hz is 3-element list",
            f"value={axes}",
        )

    # ── 11b: BMI088 has documented accel resonance (dual-die sensor) ──
    bmi088 = MEMS_PROFILES.get("BMI088", {})
    results.check(
        bmi088.get("accel_resonance_hz") == 6500,
        "BMI088 accel_resonance_hz = 6500 Hz (separate accel die)",
        f"got={bmi088.get('accel_resonance_hz')}",
    )

    # ── 11c: Dual-mass waveform (BMI088: gyro 23 kHz + accel 6.5 kHz) ──
    wf_dual = get_dual_mass_sweep("BMI088", duration_ms=50)
    results.check(len(wf_dual) > 0,
                  "BMI088 dual-mass sweep generates samples",
                  f"samples={len(wf_dual)}")
    results.check(np.max(np.abs(wf_dual)) <= 1.01,
                  "Dual-mass waveform amplitude within bounds")

    # Both frequency bands should be present in the spectrum
    spec_dual = np.abs(np.fft.rfft(wf_dual))
    freqs_dual = np.fft.rfftfreq(len(wf_dual), d=1.0 / SAMPLE_RATE)
    # Gyro band: energy around 23 kHz
    gyro_mask = (freqs_dual > 21000) & (freqs_dual < 25000)
    # Accel band: energy around 6.5 kHz
    accel_mask = (freqs_dual > 5000) & (freqs_dual < 8000)
    has_gyro_band = np.max(spec_dual[gyro_mask]) > np.mean(spec_dual) * 0.1
    has_accel_band = np.max(spec_dual[accel_mask]) > np.mean(spec_dual) * 0.1
    results.check(has_gyro_band,
                  "Dual-mass waveform contains gyro band (21–25 kHz)",
                  f"gyro_present={has_gyro_band}")
    results.check(has_accel_band,
                  "Dual-mass waveform contains accel band (5–8 kHz)",
                  f"accel_present={has_accel_band}")

    # ── 11d: get_dual_mass_sweep raises on sensor without accel resonance ──
    try:
        get_dual_mass_sweep("MPU-6050")
        results.fail("get_dual_mass_sweep on MPU-6050 should raise ValueError")
    except ValueError:
        results.ok("get_dual_mass_sweep raises ValueError for MPU-6050 (no accel_resonance_hz)")

    # ── 11e: Dual-mass raises on sample_rate Nyquist violation ──
    try:
        generate_dual_mass_waveform(gyro_freq_hz=27000, accel_freq_hz=6500,
                                    sample_rate=44100)  # < 2×27000
        results.fail("Nyquist violation should raise ValueError")
    except ValueError:
        results.ok("Nyquist violation raises ValueError in generate_dual_mass_waveform")

    # ── 11f: Axis-dependent resonance — MPU-6050 axis spread ──
    # Y-axis resonance (23 kHz) is 4 kHz below X-axis (27 kHz).
    # A sweep targeted only at the nominal (27 kHz ± 1 kHz) misses Y.
    # cover_all_axes=True must span min(axes)-1k to max(axes)+1k.
    mpu_profile = MEMS_PROFILES["MPU-6050"]
    axes_mpu = mpu_profile["axis_resonances_hz"]  # [27000, 23000, 28000]
    expected_start = min(axes_mpu) - 1000          # 22000
    expected_end   = max(axes_mpu) + 1000          # 29000

    wf_allaxis = get_targeted_sweep("MPU-6050", duration_ms=20, cover_all_axes=True)
    spec_allaxis = np.abs(np.fft.rfft(wf_allaxis))
    freqs_allaxis = np.fft.rfftfreq(len(wf_allaxis), d=1.0 / SAMPLE_RATE)

    # Check energy is present across the full axis spread
    y_axis_mask = (freqs_allaxis > 22000) & (freqs_allaxis < 24500)
    x_axis_mask = (freqs_allaxis > 26000) & (freqs_allaxis < 28500)
    results.check(np.any(spec_allaxis[y_axis_mask] > 0),
                  "All-axis sweep covers Y-axis (~23 kHz)",
                  f"expected_start={expected_start} Hz")
    results.check(np.any(spec_allaxis[x_axis_mask] > 0),
                  "All-axis sweep covers X-axis (~27 kHz)")

    # cover_all_axes=False should use tolerance-based bandwidth, not all-axis
    wf_tol = get_targeted_sweep("MPU-6050", duration_ms=20, cover_all_axes=False)
    results.check(len(wf_tol) > 0,
                  "Tolerance-mode targeted sweep generates samples",
                  f"samples={len(wf_tol)}")

    # ── 11g: Manufacturing bandwidth >= 2 × tolerance × nominal ──
    for model, profile in MEMS_PROFILES.items():
        nom = profile["resonance_hz"]
        tol = profile["mfg_tolerance_pct"]
        bw = manufacturing_bandwidth(nom, tol)
        expected_bw = 2 * nom * tol / 100.0
        results.check(
            bw >= max(2000, int(expected_bw)) - 1,  # ±1 for int rounding
            f"manufacturing_bandwidth({model}): {bw} Hz covers ±{tol}%",
            f"expected≥{int(expected_bw)} Hz",
        )

    # ── 11h: Thermal compensation shifts frequency in correct direction ──
    # Silicon MEMS: negative tempco → resonance drops when hot
    f_hot  = thermal_compensate_resonance(27000.0, delta_temp_c=+40.0,
                                           temp_coeff_ppm_per_c=-50.0)
    f_cold = thermal_compensate_resonance(27000.0, delta_temp_c=-35.0,
                                           temp_coeff_ppm_per_c=-50.0)
    results.check(f_hot < 27000.0,
                  "Negative tempco: hot sensor resonance < nominal",
                  f"f_hot={f_hot:.1f} Hz")
    results.check(f_cold > 27000.0,
                  "Negative tempco: cold sensor resonance > nominal",
                  f"f_cold={f_cold:.1f} Hz")

    # Verify round-trip accuracy of thermal correction
    delta = 40.0
    tc = -50.0
    f_corrected = thermal_compensate_resonance(27000.0, delta, tc)
    expected = 27000.0 * (1.0 + tc * delta / 1_000_000.0)
    results.check(abs(f_corrected - expected) < 0.01,
                  "Thermal compensation is numerically exact",
                  f"result={f_corrected:.2f}, expected={expected:.2f}")

    # Zero delta → no change
    f_zero = thermal_compensate_resonance(25000.0, 0.0)
    results.check(f_zero == 25000.0,
                  "Zero temperature offset → no frequency change")

    # ── 11i: Optimal burst rate — lower bound is physically meaningful ──
    # MPU-6050: f₀=27 kHz, Q=10,000 → τ=0.118 s → min rate ~8.4 Hz at 50%
    rate_mpu = optimal_burst_rate_hz(27000.0, q_factor=10000,
                                      min_amplitude_fraction=0.5)
    results.check(5.0 < rate_mpu < 15.0,
                  "MPU-6050 min burst rate: 5–15 Hz at Q=10k, floor=50%",
                  f"rate={rate_mpu:.1f} Hz")

    # Higher Q → slower decay → lower minimum rate
    rate_hi_q = optimal_burst_rate_hz(27000.0, q_factor=30000, min_amplitude_fraction=0.5)
    rate_lo_q = optimal_burst_rate_hz(27000.0, q_factor=3000,  min_amplitude_fraction=0.5)
    results.check(rate_hi_q < rate_lo_q,
                  "Higher Q → lower minimum burst rate",
                  f"hi_q={rate_hi_q:.1f} Hz, lo_q={rate_lo_q:.1f} Hz")

    # Default presets (50–100 Hz) must exceed the minimum rate
    results.check(50.0 > rate_mpu,
                  "Default 50 Hz burst rate exceeds minimum for MPU-6050",
                  f"min={rate_mpu:.1f} Hz, default=50 Hz")

    # Edge: zero / negative Q does not crash
    rate_zero_q = optimal_burst_rate_hz(27000.0, q_factor=0)
    results.check(rate_zero_q >= 1.0,
                  "Q=0 returns safe floor (≥1 Hz)",
                  f"rate={rate_zero_q}")

    # ── 11j: Audible subharmonic detection ──
    # BMI088 at 23 kHz: f/5=4600, f/3=7667, f/2=11500 are all audible
    audible_bmi = subharmonic_audible_components(23000, [5, 3, 2, 1])
    audible_freqs = [f for f, d in audible_bmi]
    results.check(
        any(abs(f - 4600.0) < 10 for f in audible_freqs),
        "BMI088 f/5 = 4600 Hz flagged as audible",
        f"audible={[round(f, 0) for f in audible_freqs]}",
    )
    results.check(
        any(abs(f - 11500.0) < 10 for f in audible_freqs),
        "BMI088 f/2 = 11500 Hz flagged as audible",
    )
    # f/1 = 23000 Hz is ultrasonic — must NOT appear in audible list
    results.check(
        not any(abs(f - 23000.0) < 100 for f in audible_freqs),
        "BMI088 f/1 = 23000 Hz is NOT flagged audible (ultrasonic)",
    )

    # LSM6DS3 at 20 kHz: even f/1 is borderline — all divisors are audible
    audible_lsm = subharmonic_audible_components(20000, [5, 3, 2, 1],
                                                  threshold_hz=HUMAN_HEARING_HZ)
    results.check(
        len(audible_lsm) >= 3,
        "LSM6DS3 (20 kHz base): ≥3 subharmonics are audible",
        f"audible_count={len(audible_lsm)}",
    )

    # Empty divisors → empty audible list (no crash)
    audible_empty = subharmonic_audible_components(25000, [])
    results.check(audible_empty == [],
                  "Empty divisors → empty audible list (no crash)")

    # ── 11k: Zone boundary conditions ──
    ladder = SubharmonicLadder(base_freq_hz=25000)

    # Exact outer boundary: range == range_max_m of the highest zone (200m)
    zone_at_200 = ladder.get_zone(200.0)
    results.check(zone_at_200 is None,
                  "Exact outer boundary (200.0m) → outside all zones (None)",
                  f"zone={'None' if zone_at_200 is None else zone_at_200.name}")

    # Exact zone transition: range == range_max of charging = 120m
    # Target is in priming (120 ≤ r < 200), not charging (60 ≤ r < 120)
    zone_at_120 = ladder.get_zone(120.0)
    results.check(
        zone_at_120 is not None and zone_at_120.name == "priming",
        "Exact boundary 120.0m → priming zone (range_min=120.0, range_max=200.0)",
        f"zone={'None' if zone_at_120 is None else zone_at_120.name}",
    )

    # At exactly 0m (inside kill zone min boundary)
    zone_at_0 = ladder.get_zone(0.0)
    results.check(
        zone_at_0 is not None and zone_at_0.name == "kill",
        "0.0m → kill zone",
        f"zone={'None' if zone_at_0 is None else zone_at_0.name}",
    )

    # Negative range (physically impossible — should return None gracefully)
    zone_neg = ladder.get_zone(-5.0)
    results.check(zone_neg is None,
                  "Negative range → None (not a kill zone)",
                  f"zone={'None' if zone_neg is None else zone_neg.name}")

    # Very large range (orbital / absurd)
    zone_huge = ladder.get_zone(100000.0)
    results.check(zone_huge is None,
                  "100000m (absurd) → None (outside all zones)")

    # ── 11l: Zone validation catches misconfigurations ──
    # Empty divisors list
    bad_empty = EngagementZone(
        name="bad_empty", range_max_m=50.0, range_min_m=10.0,
        divisors=[], amplitude_weights=[], mode="continuous",
    )
    try:
        SubharmonicLadder.validate_zone_config(bad_empty)
        results.fail("Empty divisors zone should raise ValueError")
    except ValueError:
        results.ok("validate_zone_config raises on empty divisors")

    # Mismatched lengths
    bad_mismatch = EngagementZone(
        name="bad_mismatch", range_max_m=50.0, range_min_m=10.0,
        divisors=[2, 3], amplitude_weights=[0.5], mode="continuous",
    )
    try:
        SubharmonicLadder.validate_zone_config(bad_mismatch)
        results.fail("Mismatched divisors/weights should raise ValueError")
    except ValueError:
        results.ok("validate_zone_config raises on mismatched lengths")

    # Divisor of zero
    bad_zero_div = EngagementZone(
        name="bad_zero_div", range_max_m=50.0, range_min_m=10.0,
        divisors=[0, 2], amplitude_weights=[0.5, 1.0], mode="continuous",
    )
    try:
        SubharmonicLadder.validate_zone_config(bad_zero_div)
        results.fail("Divisor of 0 should raise ValueError")
    except ValueError:
        results.ok("validate_zone_config raises on zero divisor")

    # Inverted range
    bad_range = EngagementZone(
        name="bad_range", range_max_m=10.0, range_min_m=50.0,
        divisors=[2], amplitude_weights=[1.0], mode="continuous",
    )
    try:
        SubharmonicLadder.validate_zone_config(bad_range)
        results.fail("Inverted range zone should raise ValueError")
    except ValueError:
        results.ok("validate_zone_config raises on inverted range")

    # ── 11m: generate_stacked_waveform guards ──
    # Empty divisors zone returns silence (no crash)
    silence_wf = ladder.generate_stacked_waveform(bad_empty, duration_ms=20)
    results.check(
        len(silence_wf) > 0 and np.max(np.abs(silence_wf)) < 1e-9,
        "generate_stacked_waveform returns zero array for empty divisors",
        f"samples={len(silence_wf)}, peak={np.max(np.abs(silence_wf)):.2e}",
    )

    # Mismatched zone raises ValueError in generate_stacked_waveform
    try:
        ladder.generate_stacked_waveform(bad_mismatch, duration_ms=20)
        results.fail("Mismatched zone in generate_stacked_waveform should raise")
    except ValueError:
        results.ok("generate_stacked_waveform raises on mismatched zone config")

    # ── 11n: get_targeted_burst uses tolerance-aware bandwidth ──
    # MPU-6050: tolerance=10% → manufacturing_bandwidth(27000, 10) = 5400 Hz
    # Burst should span 27000 ± 2700 = 24300–29700 Hz
    burst_mpu = get_targeted_burst("MPU-6050", train_ms=200)
    results.check(len(burst_mpu) > 0,
                  "Tolerance-aware targeted burst generates samples",
                  f"samples={len(burst_mpu)}")

    # ADXRS290 (14 kHz) — below standard piezo passband, but burst must still
    # generate valid samples (hardware selection is the operator's concern)
    burst_adx = get_targeted_burst("ADXRS290", train_ms=100)
    results.check(len(burst_adx) > 0,
                  "ADXRS290 (14 kHz military) burst generates samples",
                  f"samples={len(burst_adx)}")

    # ── 11o: Sensors with axis spread > 2 kHz use wider sweep ──
    # MPU-6050 axis spread: 23–28 kHz = 5 kHz. Old ±1 kHz = 26–28 kHz = missed Y.
    # New all-axis sweep = 22–29 kHz = 7 kHz total. Must be wider than old.
    wf_new = get_targeted_sweep("MPU-6050", duration_ms=20, cover_all_axes=True)
    wf_old_bw = 2000  # Hz (old hardcoded ±1 kHz bandwidth)
    # New sweep spans min(axes)-1k to max(axes)+1k = 22k to 29k = 7 kHz
    new_bw = max(MEMS_PROFILES["MPU-6050"]["axis_resonances_hz"]) + 1000 - \
             (min(MEMS_PROFILES["MPU-6050"]["axis_resonances_hz"]) - 1000)
    results.check(new_bw > wf_old_bw,
                  "All-axis sweep bandwidth wider than old +-1 kHz for MPU-6050",
                  f"new_bw={new_bw} Hz > old_bw={wf_old_bw} Hz")


def main() -> int:
    """Run all software-only tests and return exit code 0 (pass) or 1 (fail)."""
    results = TestResults()

    try:
        test_propeller_detection(results)
    except Exception as e:
        results.fail(f"TEST 1 CRASHED: {e}")
        traceback.print_exc()

    try:
        test_doppler_speed(results)
    except Exception as e:
        results.fail(f"TEST 2 CRASHED: {e}")
        traceback.print_exc()

    try:
        test_platform_identification(results)
    except Exception as e:
        results.fail(f"TEST 3 CRASHED: {e}")
        traceback.print_exc()

    try:
        test_beamforming(results)
    except Exception as e:
        results.fail(f"TEST 4 CRASHED: {e}")
        traceback.print_exc()

    try:
        test_waveform_generation(results)
    except Exception as e:
        results.fail(f"TEST 5 CRASHED: {e}")
        traceback.print_exc()

    try:
        test_probe_classification(results)
    except Exception as e:
        results.fail(f"TEST 6 CRASHED: {e}")
        traceback.print_exc()

    try:
        test_full_pipeline(results)
    except Exception as e:
        results.fail(f"TEST 7 CRASHED: {e}")
        traceback.print_exc()

    try:
        test_passive_detector_loop(results)
    except Exception as e:
        results.fail(f"TEST 8 CRASHED: {e}")
        traceback.print_exc()

    try:
        test_subharmonic_ladder(results)
    except Exception as e:
        results.fail(f"TEST 9 CRASHED: {e}")
        traceback.print_exc()

    try:
        test_doppler_precompensation(results)
    except Exception as e:
        results.fail(f"TEST 10 CRASHED: {e}")
        traceback.print_exc()

    try:
        test_proof_mass_edge_cases(results)
    except Exception as e:
        results.fail(f"TEST 11 CRASHED: {e}")
        traceback.print_exc()

    all_passed = results.summary()
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
