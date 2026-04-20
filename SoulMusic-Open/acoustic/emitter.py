"""
SoulMusic — acoustic/emitter.py
Hardware interface for driving ultrasonic transducer arrays.

Supports two output modes:
  1. I²S DAC — high-fidelity, uses Pi's I²S pins + external DAC board
  2. PWM — simpler, uses Pi GPIO hardware PWM (lower quality but no DAC needed)

Beamforming:
  When a BeamController is attached, the mono waveform is expanded into
  per-element phase-delayed channels before output.  This produces a
  directional beam that can be electronically steered toward the target.
  Without a BeamController, output is single-channel (omnidirectional).

The emitter runs in a background thread, continuously outputting the
configured waveform.  Commands from the operator update the sweep
parameters in real-time via thread-safe queue.
"""

import logging
import threading
import queue
import time
from dataclasses import dataclass

import numpy as np

LOG = logging.getLogger("acoustic.emitter")

# ── State ────────────────────────────────────────────────────────

_emitter_thread: threading.Thread | None = None
_command_queue: queue.Queue = queue.Queue(maxsize=16)
_running = False


@dataclass
class EmitterState:
    enabled: bool = False
    freq_start: int = 20000
    freq_end: int = 30000
    sweep_ms: int = 100
    power: float = 0.5        # 0.0–1.0 maps to transducer amplitude
    mode: str = "continuous"  # "continuous" or "burst"
    rep_rate_hz: int = 50     # burst repetition rate
    pulse_ms: float = 2.0    # burst pulse duration


_state = EmitterState()
_output_device = None  # Will be sounddevice OutputStream or GPIO PWM
_beam_controller = None  # Optional BeamController for directional output
_ladder = None  # Optional SubharmonicLadder for multi-tone stacked output
_ladder_waveform = None  # Cached stacked waveform from ladder
_ladder_zone_name = None  # Current zone name for cache invalidation


# ═══════════════════════════════════════════════════════════════
#  Public API (called from planar_host data channel handler)
# ═══════════════════════════════════════════════════════════════

def init_emitter(beam_controller=None, ladder=None):
    """Initialize the acoustic emitter hardware.

    Args:
        beam_controller: Optional BeamController from acoustic.beam.
                         If provided, output is multi-channel steered.
                         If None, output is single-channel omnidirectional.
        ladder: Optional SubharmonicLadder from acoustic.resonance.
                If provided, enables graduated multi-tone engagement.
    """
    global _emitter_thread, _running, _output_device, _beam_controller, _ladder

    _beam_controller = beam_controller
    _ladder = ladder

    # Try I²S/sounddevice first
    try:
        import sounddevice as sd
        # List available output devices
        devices = sd.query_devices()
        LOG.info(f"Audio devices: {devices}")

        # We need a device that supports ≥96kHz sample rate
        # (Nyquist for 35kHz ultrasonic output)
        _output_device = "sounddevice"
        LOG.info("Using sounddevice (I²S DAC) for acoustic output")
    except ImportError:
        LOG.info("sounddevice not available — will use PWM fallback")
        _output_device = "pwm"

    _running = True
    _emitter_thread = threading.Thread(target=_emitter_worker, daemon=True,
                                       name="acoustic-emitter")
    _emitter_thread.start()
    if _beam_controller:
        LOG.info(f"Acoustic emitter started (beamformed, "
                 f"{_beam_controller.n_elements} elements)")
    else:
        LOG.info("Acoustic emitter thread started (omnidirectional)")


def update_emitter(enabled: bool, freq_start: int, freq_end: int,
                   sweep_ms: int, power: float, mode: str = "continuous",
                   rep_rate_hz: int = 50, pulse_ms: float = 2.0):
    """Update emitter parameters (called from data channel handler).

    Args:
        mode: "continuous" (steady sweep) or "burst" (impulse pulse train)
        rep_rate_hz: Burst repetition rate (burst mode only)
        pulse_ms: Individual pulse duration in ms (burst mode only)
    """
    try:
        _command_queue.put_nowait({
            "enabled": enabled,
            "freq_start": freq_start,
            "freq_end": freq_end,
            "sweep_ms": sweep_ms,
            "power": power,
            "mode": mode,
            "rep_rate_hz": rep_rate_hz,
            "pulse_ms": pulse_ms,
        })
    except queue.Full:
        LOG.warning("Emitter command queue full — dropping update")


def update_beam(azimuth_deg: float = 0.0, elevation_deg: float = 0.0,
                focal_distance_m: float = 0.0, vortex_order: int = 0):
    """Update beam steering direction (if BeamController attached).

    Called from planar_host when operator sends beam commands or when
    the visual tracker updates target bearing.
    """
    if _beam_controller is None:
        return
    _beam_controller.aim(azimuth_deg, elevation_deg)
    if focal_distance_m > 0:
        _beam_controller.focus(focal_distance_m)
    _beam_controller.set_vortex(vortex_order)


def get_beam_status() -> dict | None:
    """Return current beam status for telemetry."""
    if _beam_controller is None:
        return None
    return _beam_controller.get_status()


def stop_emitter():
    """Shut down the emitter cleanly."""
    global _running
    _running = False
    if _emitter_thread:
        _emitter_thread.join(timeout=2.0)
    LOG.info("Acoustic emitter stopped")


def update_ladder(ladder):
    """Attach or update the subharmonic ladder on a running emitter.

    Called from planar_host when platform match retunes the ladder.
    """
    global _ladder
    _ladder = ladder


def set_ladder_zone(zone_name: str, range_m: float,
                    radial_speed_ms: float = 0.0):
    """Generate the stacked waveform for a specific engagement zone.

    Called from planar_host when detection range crosses a zone boundary.
    The waveform is cached and used by the worker thread on next cycle.

    When ``radial_speed_ms`` is provided, the waveform frequencies are
    Doppler pre-compensated so the moving target receives the intended
    resonant subharmonics.
    """
    global _ladder_waveform, _ladder_zone_name

    if _ladder is None:
        return

    zone = _ladder.get_zone(range_m)
    if zone is None or zone.name == _ladder_zone_name:
        return

    _ladder_zone_name = zone.name
    _ladder_waveform = _ladder.generate_stacked_waveform(
        zone, duration_ms=200, radial_speed_ms=radial_speed_ms)
    LOG.info(f"Ladder zone → {zone.name}: "
             f"{[f'{f:.0f}' for f in _ladder.get_zone_frequencies(zone, radial_speed_ms)]} Hz "
             f"({zone.mode}, v={radial_speed_ms:.1f} m/s)")


# ═══════════════════════════════════════════════════════════════
#  Worker Thread
# ═══════════════════════════════════════════════════════════════

def _emitter_worker():
    """Background thread: generates and outputs waveforms.

    If a SubharmonicLadder is active and has a cached zone waveform,
    it takes priority over the legacy chirp/burst generation.  This
    outputs the multi-tone stacked signal for the current engagement
    zone, automatically switching as the target closes range.
    """
    global _state

    from acoustic.resonance import generate_chirp, SweepConfig
    from acoustic.resonance import generate_burst_train, BurstConfig

    current_waveform = None
    last_config_hash = None

    while _running:
        # Check for parameter updates
        try:
            while True:
                cmd = _command_queue.get_nowait()
                _state.enabled = cmd["enabled"]
                _state.freq_start = cmd["freq_start"]
                _state.freq_end = cmd["freq_end"]
                _state.sweep_ms = cmd["sweep_ms"]
                _state.power = cmd["power"]
                _state.mode = cmd.get("mode", "continuous")
                _state.rep_rate_hz = cmd.get("rep_rate_hz", 50)
                _state.pulse_ms = cmd.get("pulse_ms", 2.0)
        except queue.Empty:
            pass

        if not _state.enabled:
            # Emitter off — sleep and check again
            time.sleep(0.05)
            continue

        # Prefer ladder stacked waveform if available
        if _ladder_waveform is not None and _ladder is not None:
            _output_waveform(_ladder_waveform * _state.power)
            continue

        # Legacy path: single-frequency chirp or burst
        config_hash = (_state.freq_start, _state.freq_end,
                       _state.sweep_ms, _state.power, _state.mode,
                       _state.rep_rate_hz, _state.pulse_ms)
        if config_hash != last_config_hash:
            if _state.mode == "burst":
                # Impulse burst mode — concentrated pulses
                burst_cfg = BurstConfig(
                    freq_start=_state.freq_start,
                    freq_end=_state.freq_end,
                    pulse_ms=_state.pulse_ms,
                    rise_ms=0.08,
                    rep_rate_hz=_state.rep_rate_hz,
                    train_duration_ms=_state.sweep_ms,  # reuse as train length
                    sample_rate=96000,
                    amplitude=_state.power,
                )
                current_waveform = generate_burst_train(burst_cfg)
                LOG.info(f"BURST mode: {_state.freq_start}–{_state.freq_end} Hz, "
                         f"{_state.pulse_ms}ms pulse @ {_state.rep_rate_hz} Hz, "
                         f"power={_state.power:.1f}")
            else:
                # Continuous sweep mode
                sweep = SweepConfig(
                    freq_start=_state.freq_start,
                    freq_end=_state.freq_end,
                    duration_ms=_state.sweep_ms,
                    sample_rate=96000,
                    amplitude=_state.power,
                    window="tukey",
                    repeat=1,
                )
                current_waveform = generate_chirp(sweep)
                LOG.info(f"CONTINUOUS mode: {_state.freq_start}–{_state.freq_end} Hz, "
                         f"{_state.sweep_ms}ms, power={_state.power:.1f}")
            last_config_hash = config_hash

        if current_waveform is None:
            time.sleep(0.01)
            continue

        # Output the waveform
        _output_waveform(current_waveform)


def _output_waveform(waveform: np.ndarray):
    """Output a single sweep cycle through the configured device.

    If a BeamController is attached, expand mono waveform into
    per-element steered channels before output.
    """
    if _beam_controller is not None:
        steered = _beam_controller.steer_waveform(waveform, sample_rate=96000)
        _output_multichannel(steered)
    elif _output_device == "sounddevice":
        _output_sounddevice(waveform)
    elif _output_device == "pwm":
        _output_pwm(waveform)
    else:
        time.sleep(0.01)


def _output_multichannel(steered: np.ndarray):
    """Output multi-channel beamformed waveform.

    Each column is one transducer element's phase-delayed signal.
    Requires a multi-channel DAC (e.g., I²S with TDM or multiple
    I²S buses, or a USB multi-channel audio interface).
    """
    try:
        import sounddevice as sd
        sd.play(steered, samplerate=96000, blocking=True)
    except Exception as e:
        LOG.error(f"Multi-channel output error: {e}")
        time.sleep(0.1)


def _output_sounddevice(waveform: np.ndarray):
    """Play waveform via sounddevice (I²S DAC output)."""
    try:
        import sounddevice as sd
        # Blocking play — waits for waveform to finish before returning
        # This naturally paces the sweep repetition
        sd.play(waveform, samplerate=96000, blocking=True)
    except Exception as e:
        LOG.error(f"Sounddevice output error: {e}")
        time.sleep(0.1)


def _output_pwm(waveform: np.ndarray):
    """Output waveform via Raspberry Pi hardware PWM.
    This is a simpler but lower-fidelity approach using GPIO.
    Requires RPi.GPIO or pigpio library."""
    try:
        # TODO: Implement PWM-based waveform output
        # For now, simulate the timing
        duration_s = len(waveform) / 96000.0
        time.sleep(duration_s)
    except Exception as e:
        LOG.error(f"PWM output error: {e}")
        time.sleep(0.1)
