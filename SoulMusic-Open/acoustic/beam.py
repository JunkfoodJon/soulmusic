"""
SoulMusic — acoustic/beam.py
Phased array beamforming: geometry, delay computation, steering, and
performance estimation for ultrasonic transducer arrays.

Physics references:
  - Van Trees, "Optimum Array Processing", Wiley 2002
  - Kino, "Acoustic Waves", Prentice-Hall 1987
  - Wooh & Shi, "Influence of phased array element size", JASA 1998
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional

SPEED_OF_SOUND = 343.0  # m/s at ~20°C, 1 atm


# ─────────────────────────────────────────────────────────────────────────────
#  Array Geometry
# ─────────────────────────────────────────────────────────────────────────────

class ArrayGeometry:
    """Positions of transducer elements in 3-D space.

    Convention: XY plane is the array face; Z points in the broadside
    direction (the direction of maximum sensitivity / output when delay = 0).
    All coordinates in metres.
    """

    def __init__(self, positions: np.ndarray):
        """
        Parameters
        ----------
        positions : (N, 3) float64
            Element (x, y, z) coordinates in metres.
        """
        positions = np.asarray(positions, dtype=np.float64)
        if positions.ndim != 2 or positions.shape[1] != 3:
            raise ValueError("positions must be shape (N, 3)")
        self._positions = positions

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def positions(self) -> np.ndarray:
        """(N, 3) element coordinate array (read-only view)."""
        return self._positions

    @property
    def n_elements(self) -> int:
        """Number of transducer elements."""
        return int(self._positions.shape[0])

    # ── Constructors ─────────────────────────────────────────────────────────

    @classmethod
    def rectangular_grid(
        cls,
        rows: int,
        cols: int,
        spacing_m: float = 0.005,
    ) -> "ArrayGeometry":
        """Create a uniform rectangular grid centred at the origin.

        Parameters
        ----------
        rows, cols : int
            Number of elements along each axis (rows × cols total elements).
        spacing_m : float
            Centre-to-centre spacing between adjacent elements (metres).
            Default 5 mm — half-wavelength at ~34 kHz in air.
        """
        if rows < 1 or cols < 1:
            raise ValueError("rows and cols must be >= 1")
        if spacing_m <= 0:
            raise ValueError("spacing_m must be positive")
        xs = (np.arange(cols) - (cols - 1) / 2.0) * spacing_m
        ys = (np.arange(rows) - (rows - 1) / 2.0) * spacing_m
        xv, yv = np.meshgrid(xs, ys)
        zv = np.zeros_like(xv)
        positions = np.stack([xv.ravel(), yv.ravel(), zv.ravel()], axis=1)
        return cls(positions)

    @classmethod
    def circular_ring(
        cls,
        n_elements: int,
        radius_m: float = 0.04,
    ) -> "ArrayGeometry":
        """Create a circular ring of elements in the XY plane centred at the origin.

        Parameters
        ----------
        n_elements : int
            Number of elements equally spaced around the ring.
        radius_m : float
            Radius of the ring in metres (default 40 mm).
        """
        if n_elements < 1:
            raise ValueError("n_elements must be >= 1")
        angles = np.linspace(0, 2 * np.pi, n_elements, endpoint=False)
        xs = radius_m * np.cos(angles)
        ys = radius_m * np.sin(angles)
        zs = np.zeros(n_elements)
        positions = np.stack([xs, ys, zs], axis=1)
        return cls(positions)


# ─────────────────────────────────────────────────────────────────────────────
#  Steering Vector
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SteeringVector:
    """Direction and optional near-field focal distance for beam steering.

    Coordinate convention (standard acoustic phased array):
      azimuth   — rotation in the XZ plane; 0° = broadside (+Z direction)
      elevation — tilt above the XZ plane; positive toward +Y
    """

    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    focal_distance_m: float = 0.0   # 0 = far-field (plane wave)

    @property
    def unit_vector(self) -> np.ndarray:
        """Unit direction vector in 3-D (x, y, z)."""
        az = np.deg2rad(self.azimuth_deg)
        el = np.deg2rad(self.elevation_deg)
        x = np.sin(az) * np.cos(el)
        y = np.sin(el)
        z = np.cos(az) * np.cos(el)
        return np.array([x, y, z], dtype=np.float64)


# ─────────────────────────────────────────────────────────────────────────────
#  BeamFormer
# ─────────────────────────────────────────────────────────────────────────────

class BeamFormer:
    """Computes per-element time delays for phased array steering.

    Far-field (plane-wave) model:
        delay_i = -(pos_i · direction_unit) / c
        Zero-mean normalised so the centroid element has zero delay.

    Near-field (spherical-wave) model (focal_distance_m > 0):
        delay_i = (ref_dist − dist(pos_i, focal_point)) / c
        where ref_dist = ‖centroid − focal_point‖.
        Positive delay → the element fires *later*, so energy converges
        at the focal point simultaneously from all elements.
    """

    def __init__(self, geometry: ArrayGeometry):
        self._geom = geometry

    @property
    def geometry(self) -> ArrayGeometry:
        return self._geom

    def compute_delays(
        self,
        steer: SteeringVector,
        freq_hz: float,
    ) -> np.ndarray:
        """Return per-element time delays in seconds, shape (N,).

        Parameters
        ----------
        steer : SteeringVector
            Desired steering direction / focus.
        freq_hz : float
            Operating frequency (Hz).  Used for wavelength-related checks
            but the returned delays are frequency-independent for geometric
            far-field steering.  (Near-field focusing ignores freq_hz.)

        Returns
        -------
        np.ndarray, shape (N,)
            Delay in seconds for each element.  Positive = fire later.
        """
        c = SPEED_OF_SOUND
        pos = self._geom.positions

        if steer.focal_distance_m > 0.0:
            # Near-field: each element delay chosen so the wavefront
            # converges at the focal point.
            focal_pt = steer.focal_distance_m * steer.unit_vector
            dists = np.linalg.norm(pos - focal_pt, axis=1)
            # Reference: distance from array centroid to focal point
            ref_dist = float(np.linalg.norm(np.mean(pos, axis=0) - focal_pt))
            delays = (ref_dist - dists) / c
        else:
            # Far-field: project element positions onto steering direction
            delays = -(pos @ steer.unit_vector) / c
            delays -= delays.mean()

        return delays.astype(np.float64)

    def apply_to_waveform(
        self,
        mono: np.ndarray,
        delays: np.ndarray,
        sample_rate: int,
    ) -> np.ndarray:
        """Apply per-element delays to a mono waveform → (samples, N) multi-channel.

        Each column is the mono signal time-shifted by the corresponding
        element delay (fractional-sample via linear interpolation).
        """
        n_samples = len(mono)
        n_elem = len(delays)
        out = np.zeros((n_samples, n_elem), dtype=np.float32)
        t_indices = np.arange(n_samples, dtype=np.float64)

        for i in range(n_elem):
            shift_samples = delays[i] * sample_rate
            shifted_idx = t_indices - shift_samples
            shifted_idx = np.clip(shifted_idx, 0, n_samples - 1)
            idx_lo = shifted_idx.astype(np.intp)
            frac = shifted_idx - idx_lo
            idx_hi = np.minimum(idx_lo + 1, n_samples - 1)
            out[:, i] = (mono[idx_lo] * (1.0 - frac) + mono[idx_hi] * frac).astype(np.float32)

        return out

    def beamform_receive(
        self,
        multichannel: np.ndarray,
        delays: np.ndarray,
        sample_rate: int,
    ) -> np.ndarray:
        """Sum-and-delay receive beamforming → 1-D output.

        Reverses the per-element delays then sums across elements to
        coherently combine on-axis signals.
        """
        n_samples, n_elem = multichannel.shape
        out = np.zeros(n_samples, dtype=np.float64)
        t_indices = np.arange(n_samples, dtype=np.float64)

        for i in range(n_elem):
            shift_samples = -delays[i] * sample_rate  # reverse delay
            shifted_idx = t_indices - shift_samples
            shifted_idx = np.clip(shifted_idx, 0, n_samples - 1)
            idx_lo = shifted_idx.astype(np.intp)
            frac = shifted_idx - idx_lo
            idx_hi = np.minimum(idx_lo + 1, n_samples - 1)
            channel = multichannel[:, i].astype(np.float64)
            out += channel[idx_lo] * (1.0 - frac) + channel[idx_hi] * frac

        return (out / n_elem).astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
#  BeamController
# ─────────────────────────────────────────────────────────────────────────────

class BeamController:
    """Stateful wrapper around BeamFormer for use in the emitter pipeline.

    Maintains the current steering direction and operating frequency,
    recalculates delays on update, and exposes them for the audio driver
    to apply per-channel phase offsets.
    """

    def __init__(
        self,
        geometry: ArrayGeometry,
        freq_hz: float = 25_000.0,
        azimuth_deg: float = 0.0,
        elevation_deg: float = 0.0,
        focal_distance_m: float = 0.0,
    ):
        self._bf = BeamFormer(geometry)
        self._freq_hz = float(freq_hz)
        self._steer = SteeringVector(
            azimuth_deg=azimuth_deg,
            elevation_deg=elevation_deg,
            focal_distance_m=focal_distance_m,
        )
        self._delays: np.ndarray = self._bf.compute_delays(
            self._steer, self._freq_hz
        )

    # ── Mutation ─────────────────────────────────────────────────────────────

    def set_steering(
        self,
        azimuth_deg: float,
        elevation_deg: float,
        focal_distance_m: float = 0.0,
    ) -> None:
        """Update steering direction; recomputes delays immediately."""
        self._steer = SteeringVector(
            azimuth_deg=azimuth_deg,
            elevation_deg=elevation_deg,
            focal_distance_m=focal_distance_m,
        )
        self._delays = self._bf.compute_delays(self._steer, self._freq_hz)

    def set_frequency(self, freq_hz: float) -> None:
        """Update operating frequency; recomputes delays immediately."""
        self._freq_hz = float(freq_hz)
        self._delays = self._bf.compute_delays(self._steer, self._freq_hz)

    # ── Read-only state ───────────────────────────────────────────────────────

    @property
    def delays(self) -> np.ndarray:
        """Current per-element delays in seconds, shape (N,)."""
        return self._delays

    @property
    def n_elements(self) -> int:
        return self._bf.geometry.n_elements

    @property
    def azimuth_deg(self) -> float:
        return self._steer.azimuth_deg

    @property
    def elevation_deg(self) -> float:
        return self._steer.elevation_deg

    @property
    def freq_hz(self) -> float:
        return self._freq_hz

    def aim(self, azimuth_deg: float, elevation_deg: float) -> None:
        """Convenience: steer to azimuth/elevation, keeping current focal distance."""
        self.set_steering(azimuth_deg, elevation_deg, self._steer.focal_distance_m)

    def focus(self, distance_m: float) -> None:
        """Convenience: set near-field focal distance, keeping current direction."""
        self.set_steering(self._steer.azimuth_deg, self._steer.elevation_deg, distance_m)

    def get_status(self) -> dict:
        """Return current controller state as a plain dict."""
        return {
            "azimuth_deg": self._steer.azimuth_deg,
            "elevation_deg": self._steer.elevation_deg,
            "focal_distance_m": self._steer.focal_distance_m,
            "freq_hz": self._freq_hz,
            "n_elements": self.n_elements,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Performance Estimation
# ─────────────────────────────────────────────────────────────────────────────

def estimate_beamwidth(geometry: ArrayGeometry, freq_hz: float) -> float:
    """Estimate the 3-dB beamwidth of the array in degrees.

    Uses the standard uniform aperture formula for broadside radiation:
        BW_3dB ≈ 2 · arcsin(0.886 · λ / L)   (degrees)

    For a 2-D rectangular array the reported value is the beamwidth
    along the *longer* aperture axis (narrowest beam).
    Returns 180.0 for a single-element array.

    Parameters
    ----------
    geometry : ArrayGeometry
    freq_hz : float  — operating frequency in Hz

    Returns
    -------
    float  — 3-dB beamwidth in degrees
    """
    n = geometry.n_elements
    if n <= 1:
        return 180.0

    wavelength = SPEED_OF_SOUND / freq_hz
    pos = geometry.positions
    lx = float(pos[:, 0].max() - pos[:, 0].min())
    ly = float(pos[:, 1].max() - pos[:, 1].min())
    aperture = max(lx, ly)

    if aperture < 1e-12:
        return 180.0

    sin_half = min(0.443 * wavelength / aperture, 1.0)
    bw_rad = 2.0 * np.arcsin(sin_half)
    return float(np.rad2deg(bw_rad))


def estimate_gain_db(geometry: ArrayGeometry) -> float:
    """Coherent transmit gain relative to a single element (dB).

    When N elements are driven coherently, the pressure at the focal
    point (or along the broadside direction for a far-field array)
    scales linearly with N.  Power scales as N², giving:
        G = 20 · log10(N)  dB

    Parameters
    ----------
    geometry : ArrayGeometry

    Returns
    -------
    float  — coherent gain in dB
    """
    n = geometry.n_elements
    if n <= 0:
        return 0.0
    return float(10.0 * np.log10(max(n, 1)))


def estimate_focal_gain_db(
    geometry: ArrayGeometry,
    focal_distance_m: float,
    freq_hz: float,
) -> float:
    """Additional intensity gain from near-field focusing (dB).

    A focused aperture concentrates energy at the focal point beyond the
    far-field radiation pattern maximum.  The near-field (Fresnel) intensity
    enhancement is estimated from the Rayleigh distance ratio:

        z_R = D² / (4 · λ)   — Rayleigh distance of aperture D
        G_focus ≈ max(0, 10 · log10(z_R / R_f))   dB

    Returns 0 if R_f ≥ z_R (far-field focus — no extra gain).
    Capped at 20 dB (practical hardware / saturation limit).

    Parameters
    ----------
    geometry : ArrayGeometry
    focal_distance_m : float  — intended focal distance in metres
    freq_hz : float           — operating frequency in Hz

    Returns
    -------
    float  — additional focusing gain in dB (≥ 0)
    """
    if focal_distance_m <= 0.0:
        return 0.0

    wavelength = SPEED_OF_SOUND / freq_hz
    pos = geometry.positions
    lx = float(pos[:, 0].max() - pos[:, 0].min())
    ly = float(pos[:, 1].max() - pos[:, 1].min())
    aperture = max(lx, ly)

    if aperture < 1e-12:
        return 0.0

    rayleigh_distance = aperture ** 2 / (4.0 * wavelength)

    gain = 10.0 * np.log10(1.0 + rayleigh_distance / focal_distance_m)
    return float(min(gain, 20.0))
