"""
SoulMusic — detection/acoustic_detect.py
UAS/drone platform database for acoustic signature detection.

Each entry captures the acoustic and mechanical parameters used to:
  1. Identify a platform from its blade passage frequency (BPF) signature.
  2. Select the correct MEMS resonance target frequency.
  3. Choose the appropriate shell transmission preset.

BPF range is derived from motor RPM at typical operating thrust levels.
MEMS sensor entries reference published research resonant frequencies:
  InvenSense MPU-6000/6050  ~27 kHz
  InvenSense MPU-6500        ~26 kHz
  InvenSense MPU-9250        ~27 kHz
  InvenSense ICM-20689       ~24 kHz
  InvenSense ICM-42688-P     ~25 kHz
  TDK IIM-42652              ~25 kHz
  Bosch BMI055               ~22 kHz
  Bosch BMI088               ~23 kHz
  STMicro LSM6DS3/DSM        ~20 kHz
  Analog Devices ADXRS450    ~32 kHz
  Analog Devices ADIS16488   ~28 kHz
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Callable, List
import threading
import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
#  Platform Profile
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PlatformProfile:
    """Acoustic and mechanical signature of a drone/UAS platform."""

    category: str                           # "commercial"|"military"|"hobby"|"unknown"
    motor_count: int                        # total propulsion motors
    blade_count: int                        # blades per motor/propeller
    bpf_range_hz: Tuple[int, int]           # blade passage frequency range (Hz)
    mems_sensor: Optional[str]              # primary MEMS gyro model on flight controller
    shell_class: str                        # matches key in acoustic.probe.SHELL_PRESETS
    description: str = ""


# ─────────────────────────────────────────────────────────────────────────────
#  Platform Database
#  Key: short platform identifier  Value: PlatformProfile
# ─────────────────────────────────────────────────────────────────────────────

PLATFORM_DB: Dict[str, PlatformProfile] = {

    # ── DJI Commercial ───────────────────────────────────────────────────────

    "dji_mini_3_pro": PlatformProfile(
        category="commercial", motor_count=4, blade_count=3,
        bpf_range_hz=(120, 280),
        mems_sensor="TDK IIM-42652",
        shell_class="plastic",
        description="DJI Mini 3 Pro — 249 g foldable, obstacle avoidance. "
                    "IIM-42652 resonance target ~25 kHz.",
    ),
    "dji_mavic_3": PlatformProfile(
        category="commercial", motor_count=4, blade_count=3,
        bpf_range_hz=(110, 260),
        mems_sensor="TDK IIM-42652",
        shell_class="composite",
        description="DJI Mavic 3 — Hasselblad camera, magnesium alloy arms, "
                    "foldable composite body.",
    ),
    "dji_air_3": PlatformProfile(
        category="commercial", motor_count=4, blade_count=3,
        bpf_range_hz=(115, 270),
        mems_sensor="InvenSense ICM-42688-P",
        shell_class="plastic",
        description="DJI Air 3 — dual camera, under 600 g, foldable design.",
    ),
    "dji_phantom_4_pro": PlatformProfile(
        category="commercial", motor_count=4, blade_count=2,
        bpf_range_hz=(90, 220),
        mems_sensor="InvenSense MPU-6500",
        shell_class="plastic",
        description="DJI Phantom 4 Pro — fixed rigid body, white ABS shell, "
                    "1-inch Exmor sensor.",
    ),
    "dji_matrice_300_rtk": PlatformProfile(
        category="commercial", motor_count=4, blade_count=2,
        bpf_range_hz=(80, 185),
        mems_sensor="InvenSense ICM-20689",
        shell_class="composite",
        description="DJI Matrice 300 RTK — enterprise IP45, 55 min endurance, "
                    "payload up to 2.7 kg.",
    ),
    "dji_inspire_2": PlatformProfile(
        category="commercial", motor_count=4, blade_count=2,
        bpf_range_hz=(95, 215),
        mems_sensor="InvenSense MPU-9250",
        shell_class="composite",
        description="DJI Inspire 2 — cinema platform, carbon fibre arms, "
                    "interchangeable camera system.",
    ),
    "dji_mini_4_pro": PlatformProfile(
        category="commercial", motor_count=4, blade_count=3,
        bpf_range_hz=(125, 290),
        mems_sensor="TDK IIM-42652",
        shell_class="plastic",
        description="DJI Mini 4 Pro — 249 g, 4K/60fps, omnidirectional obstacle sensing.",
    ),

    # ── Autel Robotics ───────────────────────────────────────────────────────

    "autel_evo_lite_plus": PlatformProfile(
        category="commercial", motor_count=4, blade_count=3,
        bpf_range_hz=(125, 295),
        mems_sensor="Bosch BMI088",
        shell_class="plastic",
        description="Autel EVO Lite+ — 249 g foldable, 6K CMOS, orange livery.",
    ),
    "autel_evo_2_pro": PlatformProfile(
        category="commercial", motor_count=4, blade_count=3,
        bpf_range_hz=(110, 265),
        mems_sensor="Bosch BMI088",
        shell_class="plastic",
        description="Autel EVO II Pro — 6K Rubin sensor, 3-axis gimbal.",
    ),
    "autel_evo_2_enterprise": PlatformProfile(
        category="commercial", motor_count=4, blade_count=3,
        bpf_range_hz=(105, 255),
        mems_sensor="Bosch BMI088",
        shell_class="plastic",
        description="Autel EVO II Enterprise — NDAA compliant, modular payload bay.",
    ),

    # ── Parrot ───────────────────────────────────────────────────────────────

    "parrot_anafi_usa": PlatformProfile(
        category="commercial", motor_count=4, blade_count=2,
        bpf_range_hz=(130, 305),
        mems_sensor="STMicro LSM6DSM",
        shell_class="plastic",
        description="Parrot ANAFI USA — NDAA compliant, thermal + RGB, "
                    "35× zoom, LSM6DSM resonance target ~20 kHz.",
    ),
    "parrot_anafi_ai": PlatformProfile(
        category="commercial", motor_count=4, blade_count=2,
        bpf_range_hz=(150, 290),
        mems_sensor="STMicro LSM6DSM",
        shell_class="plastic",
        description="Parrot ANAFI Ai — 4G connected, 48 MP spherical camera.",
    ),

    # ── Skydio ───────────────────────────────────────────────────────────────

    "skydio_2_plus": PlatformProfile(
        category="commercial", motor_count=4, blade_count=2,
        bpf_range_hz=(140, 330),
        mems_sensor="InvenSense ICM-20689",
        shell_class="composite",
        description="Skydio 2+ — six 4K nav cameras, autonomous avoidance.",
    ),
    "skydio_x10": PlatformProfile(
        category="commercial", motor_count=4, blade_count=2,
        bpf_range_hz=(100, 245),
        mems_sensor="TDK IIM-42652",
        shell_class="composite",
        description="Skydio X10 — NDAA compliant, 50 MP + MWIR thermal, enterprise.",
    ),

    # ── Hobby / FPV ──────────────────────────────────────────────────────────

    "generic_5inch_fpv": PlatformProfile(
        category="hobby", motor_count=4, blade_count=3,
        bpf_range_hz=(300, 900),
        mems_sensor="InvenSense MPU-6000",
        shell_class="none",
        description="Generic 5-inch freestyle FPV — open carbon frame, "
                    "Betaflight F4/F7 FC, high RPM.",
    ),
    "generic_3inch_fpv": PlatformProfile(
        category="hobby", motor_count=4, blade_count=3,
        bpf_range_hz=(400, 1200),
        mems_sensor="InvenSense MPU-6000",
        shell_class="none",
        description="3-inch micro FPV — ultra-high RPM, sub-250 g, open frame.",
    ),
    "dji_fpv_combo": PlatformProfile(
        category="hobby", motor_count=4, blade_count=3,
        bpf_range_hz=(250, 750),
        mems_sensor="InvenSense ICM-42688-P",
        shell_class="plastic",
        description="DJI FPV Combo — integrated goggles, hard-mounted propellers, "
                    "O3 video link.",
    ),
    "iflight_nazgul5_hd": PlatformProfile(
        category="hobby", motor_count=4, blade_count=3,
        bpf_range_hz=(320, 960),
        mems_sensor="InvenSense MPU-6000",
        shell_class="none",
        description="iFlight Nazgul5 HD — 5-inch, DJI O3 Air Unit, "
                    "open carbon fibre frame.",
    ),
    "betafpv_cetus_pro": PlatformProfile(
        category="hobby", motor_count=4, blade_count=3,
        bpf_range_hz=(500, 1800),
        mems_sensor="InvenSense MPU-6000",
        shell_class="foam",
        description="BetaFPV Cetus Pro — 65 mm toothpick, foam prop guards, "
                    "beginner indoor FPV.",
    ),

    # ── Military / Government ─────────────────────────────────────────────────

    "aerovironment_rq11_raven": PlatformProfile(
        category="military", motor_count=1, blade_count=2,
        bpf_range_hz=(60, 130),
        mems_sensor="Analog Devices ADXRS450",
        shell_class="composite",
        description="AeroVironment RQ-11B Raven — hand-launched fixed-wing SUAS, "
                    "1.9 kg, 90 min endurance.",
    ),
    "aerovironment_switchblade_300": PlatformProfile(
        category="military", motor_count=1, blade_count=2,
        bpf_range_hz=(70, 150),
        mems_sensor="Analog Devices ADIS16488",
        shell_class="composite",
        description="AeroVironment Switchblade 300 — loitering munition, "
                    "tube-launched, anti-personnel warhead.",
    ),
    "shield_ai_v_bat": PlatformProfile(
        category="military", motor_count=1, blade_count=3,
        bpf_range_hz=(80, 200),
        mems_sensor="Analog Devices ADIS16488",
        shell_class="composite",
        description="Shield AI V-BAT — tail-sitter VTOL SUAS, 18 kg, "
                    "GPS-denied autonomous operation.",
    ),
    "textron_aerosonde_mk47": PlatformProfile(
        category="military", motor_count=1, blade_count=2,
        bpf_range_hz=(40, 100),
        mems_sensor="Analog Devices ADIS16488",
        shell_class="composite",
        description="Textron Aerosonde Mk 4.7 — fixed-wing UAS, 13.5 kg MTOW, "
                    "ISR payload.",
    ),

    # ── Unknown / Generic ─────────────────────────────────────────────────────

    "unknown_quadcopter": PlatformProfile(
        category="unknown", motor_count=4, blade_count=2,
        bpf_range_hz=(80, 400),
        mems_sensor=None,
        shell_class="unknown",
        description="Unidentified quadcopter — generic BPF signature matching.",
    ),
    "unknown_hexacopter": PlatformProfile(
        category="unknown", motor_count=6, blade_count=2,
        bpf_range_hz=(70, 360),
        mems_sensor=None,
        shell_class="unknown",
        description="Unidentified hexacopter — increased motor count signature.",
    ),
    "unknown_fixed_wing": PlatformProfile(
        category="unknown", motor_count=1, blade_count=2,
        bpf_range_hz=(40, 150),
        mems_sensor=None,
        shell_class="unknown",
        description="Unidentified fixed-wing UAS — single motor, low BPF.",
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
#  Detection Result Types
# ─────────────────────────────────────────────────────────────────────────────

SPEED_OF_SOUND = 343.0  # m/s at sea level, 20 °C


@dataclass
class DetectionResult:
    """Output of detect_propeller_signature()."""
    detected: bool = False
    confidence: float = 0.0
    fundamental_hz: float = 0.0
    harmonic_count: int = 0
    estimated_range_m: float = 0.0
    peak_amplitudes: List[float] = field(default_factory=list)


@dataclass
class PlatformMatch:
    """Output of identify_platform()."""
    platform: "PlatformMatchEntry" = None          # type: ignore[assignment]
    match_confidence: float = 0.0
    matched_by: str = ""
    mems_sensor: Optional[str] = None
    recommended_freq_hz: int = 0
    shell_class: str = "unknown"
    preloaded: bool = False


@dataclass
class PlatformMatchEntry:
    """Lightweight reference to a matched platform."""
    platform_id: str = ""
    profile: Optional[PlatformProfile] = None


# ─────────────────────────────────────────────────────────────────────────────
#  Core Detection Functions
# ─────────────────────────────────────────────────────────────────────────────

def detect_propeller_signature(
    audio: np.ndarray,
    sample_rate: int,
    min_bpf_hz: float = 30.0,
    max_bpf_hz: float = 5000.0,
    min_harmonics: int = 2,
    confidence_threshold: float = 0.35,
) -> DetectionResult:
    """Detect propeller blade-passage frequency via FFT harmonic analysis.

    Finds a fundamental frequency with at least *min_harmonics* harmonic
    peaks in the spectrum, scoring confidence based on harmonic regularity
    and SNR.

    Returns a DetectionResult (detected=True if a propeller-like harmonic
    series is found above the confidence threshold).
    """
    result = DetectionResult()
    n = len(audio)
    if n < 64:
        return result

    # Zero-pad to next power of 2 for clean FFT bins
    nfft = 1
    while nfft < n:
        nfft <<= 1

    # Apply Hann window to reduce spectral leakage
    windowed = audio * np.hanning(n)
    spectrum = np.abs(np.fft.rfft(windowed, n=nfft))
    freqs = np.fft.rfftfreq(nfft, d=1.0 / sample_rate)

    # Restrict to BPF search range
    lo_bin = max(1, int(min_bpf_hz * nfft / sample_rate))
    hi_bin = min(len(spectrum) - 1, int(max_bpf_hz * nfft / sample_rate))
    if lo_bin >= hi_bin:
        return result

    # Noise floor: median of full spectrum
    noise_floor = float(np.median(spectrum[lo_bin:hi_bin])) + 1e-12

    # Find candidate fundamental: strongest peak in BPF range
    search_region = spectrum[lo_bin:hi_bin]
    peak_idx_local = int(np.argmax(search_region))
    peak_idx = peak_idx_local + lo_bin
    fundamental_hz = freqs[peak_idx]
    peak_amp = float(spectrum[peak_idx])

    if peak_amp < noise_floor * 3:
        return result

    # Count harmonics (2f, 3f, 4f, ...) that exist above noise.
    # Require each harmonic to be significant relative to the fundamental,
    # not just above noise — this rejects spectral leakage from single tones.
    harmonic_count = 0
    peak_amplitudes = [peak_amp]
    max_harmonic = 10
    harmonic_threshold = max(noise_floor * 3.0, peak_amp * 0.02)
    for h in range(2, max_harmonic + 1):
        h_freq = fundamental_hz * h
        if h_freq >= sample_rate / 2:
            break
        h_bin = int(round(h_freq * nfft / sample_rate))
        # Search ±3 bins around expected harmonic
        search_lo = max(0, h_bin - 3)
        search_hi = min(len(spectrum), h_bin + 4)
        local_peak = float(np.max(spectrum[search_lo:search_hi]))
        if local_peak > harmonic_threshold:
            harmonic_count += 1
            peak_amplitudes.append(local_peak)

    total_harmonics = 1 + harmonic_count  # fundamental + overtones

    if total_harmonics < min_harmonics:
        return result

    # Confidence: weighted by harmonic count, SNR, and harmonic regularity
    snr = peak_amp / noise_floor
    snr_score = min(1.0, snr / 30.0)
    harmonic_score = min(1.0, harmonic_count / 4.0)

    # Harmonic decay regularity: real propellers have monotonically
    # decaying harmonics. Score 1.0 if mostly decaying.
    if len(peak_amplitudes) >= 2:
        decays = sum(1 for i in range(1, len(peak_amplitudes))
                     if peak_amplitudes[i] <= peak_amplitudes[i - 1] * 1.2)
        decay_score = decays / (len(peak_amplitudes) - 1)
    else:
        decay_score = 0.5

    confidence = 0.4 * snr_score + 0.35 * harmonic_score + 0.25 * decay_score

    detected = confidence >= confidence_threshold and total_harmonics >= min_harmonics

    # Range estimation from RMS amplitude (inverse-square law heuristic).
    # Use signal RMS rather than FFT bin magnitude for stable range.
    # Reference: RMS 0.10 ≈ 10 m.
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    ref_rms = 0.10
    ref_range = 10.0
    if rms > 1e-9:
        estimated_range = ref_range * (ref_rms / rms) ** 0.5
        estimated_range = max(0.5, min(estimated_range, 5000.0))
    else:
        estimated_range = 5000.0

    result.detected = detected
    result.confidence = confidence
    result.fundamental_hz = fundamental_hz
    result.harmonic_count = total_harmonics
    result.estimated_range_m = estimated_range
    result.peak_amplitudes = peak_amplitudes
    return result


def measure_doppler_shift(
    audio_t1: np.ndarray,
    audio_t2: np.ndarray,
    reference_freq_hz: float,
    sample_rate: int,
) -> Tuple[float, float, float]:
    """Measure Doppler shift between two consecutive audio captures.

    Compares the peak frequency near *reference_freq_hz* in each buffer
    to estimate radial speed.

    Returns:
        (shift_hz, estimated_speed_ms, corrected_fundamental_hz)
    """
    def _peak_near(audio: np.ndarray, target_hz: float) -> float:
        n = len(audio)
        nfft = 1
        while nfft < n:
            nfft <<= 1
        windowed = audio * np.hanning(n)
        spec = np.abs(np.fft.rfft(windowed, n=nfft))
        freqs = np.fft.rfftfreq(nfft, d=1.0 / sample_rate)
        # Search ±15% around target
        lo = max(1, int(target_hz * 0.85 * nfft / sample_rate))
        hi = min(len(spec) - 1, int(target_hz * 1.15 * nfft / sample_rate))
        if lo >= hi:
            return target_hz
        region = spec[lo:hi]
        peak_local = int(np.argmax(region))
        return float(freqs[lo + peak_local])

    f1 = _peak_near(audio_t1, reference_freq_hz)
    f2 = _peak_near(audio_t2, reference_freq_hz)

    avg_freq = (f1 + f2) / 2.0
    shift_hz = f2 - f1

    # Doppler: f_observed = f_true × c / (c - v)
    # → v = c × (f_obs - f_true) / f_obs
    # We estimate the true BPF from the average of two measurements
    # corrected for Doppler.
    if avg_freq > 0:
        # Estimate speed from the average observed frequency vs reference
        doppler_ratio = avg_freq / reference_freq_hz
        if abs(doppler_ratio - 1.0) > 0.001:
            estimated_speed = SPEED_OF_SOUND * (1.0 - 1.0 / doppler_ratio)
        else:
            estimated_speed = 0.0

        # Corrected fundamental: remove Doppler shift
        corrected = avg_freq / max(doppler_ratio, 0.5)
    else:
        estimated_speed = 0.0
        corrected = reference_freq_hz

    return (shift_hz, estimated_speed, corrected)


def identify_platform(
    detection: DetectionResult,
    radial_speed: float = 0.0,
    platform_db: Optional[Dict[str, PlatformProfile]] = None,
) -> PlatformMatch:
    """Match a detection result to a platform in the database.

    Corrects the observed frequency for Doppler shift before matching
    against each platform's BPF range. Resolves MEMS sensor and
    attack frequency when a match is found.
    """
    if platform_db is None:
        platform_db = PLATFORM_DB

    # Lazy import to avoid circular dependency
    from acoustic.resonance import MEMS_PROFILES

    # Correct for Doppler: f_true = f_obs × (c - v) / c
    if abs(radial_speed) > 0.01:
        clamped_v = max(-0.95 * SPEED_OF_SOUND,
                        min(0.95 * SPEED_OF_SOUND, radial_speed))
        corrected_bpf = detection.fundamental_hz * (SPEED_OF_SOUND - clamped_v) / SPEED_OF_SOUND
    else:
        corrected_bpf = detection.fundamental_hz

    best_match = PlatformMatch()
    best_score = -1.0

    for pid, profile in platform_db.items():
        lo, hi = profile.bpf_range_hz
        if lo <= corrected_bpf <= hi:
            # Score: how centred is the detection within the range?
            mid = (lo + hi) / 2.0
            span = (hi - lo) / 2.0
            offset = abs(corrected_bpf - mid) / span if span > 0 else 1.0
            range_score = 1.0 - offset  # 1.0 at centre, 0.0 at edge

            # Bonus for higher detection confidence
            score = 0.6 * range_score + 0.4 * detection.confidence

            if score > best_score:
                best_score = score
                entry = PlatformMatchEntry(platform_id=pid, profile=profile)

                # Resolve MEMS sensor
                mems = profile.mems_sensor
                mems_key = None
                recommended_freq = 0
                preloaded = False

                if mems:
                    # Strip manufacturer prefix to match MEMS_PROFILES keys
                    # e.g. "InvenSense MPU-6500" → "MPU-6500"
                    parts = mems.split()
                    short = parts[-1] if parts else mems
                    # Try exact match first, then prefix match for
                    # partial names like "LSM6DSM" → "LSM6DSMTR",
                    # or "MPU-6000" → "MPU-6050" (same family)
                    for candidate in [mems, short]:
                        if candidate in MEMS_PROFILES:
                            mems_key = candidate
                            break
                    if mems_key is None:
                        # Prefix match: find first key starting with short
                        for pk in MEMS_PROFILES:
                            if pk.startswith(short) or short.startswith(pk):
                                mems_key = pk
                                break
                    if mems_key is not None:
                        recommended_freq = MEMS_PROFILES[mems_key]["resonance_hz"]
                        preloaded = True

                best_match = PlatformMatch(
                    platform=entry,
                    match_confidence=score,
                    matched_by="bpf_range",
                    mems_sensor=mems_key,
                    recommended_freq_hz=recommended_freq,
                    shell_class=profile.shell_class,
                    preloaded=preloaded,
                )

    # If nothing matched, return unknown
    if best_match.platform is None:
        unknown_entry = PlatformMatchEntry(platform_id="unknown", profile=None)
        best_match = PlatformMatch(
            platform=unknown_entry,
            match_confidence=0.0,
            matched_by="none",
        )

    return best_match


# ─────────────────────────────────────────────────────────────────────────────
#  Passive Detector (background capture loop)
# ─────────────────────────────────────────────────────────────────────────────

class PassiveDetector:
    """Background thread that continuously captures audio and runs detection.

    Calls *on_detection* for every positive detection and *on_platform_match*
    when a platform is identified with a pre-loaded attack frequency.
    """

    def __init__(
        self,
        on_detection: Optional[Callable] = None,
        on_platform_match: Optional[Callable] = None,
        capture_duration_ms: float = 100.0,
        sample_rate: int = 96000,
    ):
        self._on_detection = on_detection
        self._on_platform_match = on_platform_match
        self._capture_ms = capture_duration_ms
        self._sample_rate = sample_rate
        self._capture_func: Optional[Callable] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._prev_audio: Optional[np.ndarray] = None

    def set_hardware(self, capture_func: Callable):
        """Set the audio capture function: capture_func(duration_ms) → ndarray."""
        self._capture_func = capture_func

    def start(self):
        if self._running or self._capture_func is None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._prev_audio = None

    def _loop(self):
        while self._running:
            try:
                audio = self._capture_func(self._capture_ms)
                det = detect_propeller_signature(audio, self._sample_rate)

                if det.detected:
                    if self._on_detection:
                        self._on_detection(det)

                    # Doppler from consecutive frames
                    if self._prev_audio is not None:
                        _, speed, _ = measure_doppler_shift(
                            self._prev_audio, audio,
                            det.fundamental_hz, self._sample_rate)
                    else:
                        speed = 0.0

                    match = identify_platform(det, radial_speed=speed)
                    if match.match_confidence > 0.1 and self._on_platform_match:
                        self._on_platform_match(match)

                self._prev_audio = audio
            except Exception:
                pass  # capture/detection failure — continue loop
