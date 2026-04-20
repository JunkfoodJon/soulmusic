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

from dataclasses import dataclass
from typing import Optional, Tuple, Dict


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
        bpf_range_hz=(120, 285),
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
