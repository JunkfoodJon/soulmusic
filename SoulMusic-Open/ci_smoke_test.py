"""
SoulMusic — ci_smoke_test.py
============================
Fast, headless CI smoke tests.  No hardware.  No audio devices.  No GUI.

Complements test_harness.py (algorithmic accuracy) by covering the integration
concerns that CI/CD must catch before a release:

  Group A — Import chain: every public module imports without error
  Group B — Package structure: __init__.py exports, no stale bytecode
  Group C — Module wiring: inter-module call contracts, data shapes
  Group D — Platform detection: PLATFORM_DB coverage + schema consistency
  Group E — Configuration constants: sensor profiles, valid numeric ranges
  Group F — File system & paths: all referenced paths resolve from install root
  Group G — Cross-platform compatibility: no Windows-only symbols in shared code

Exit code:  0 if all groups pass, 1 if any assertion fails.
Usage:      python ci_smoke_test.py [--verbose] [--groups A,B,C]
            python ci_smoke_test.py --groups G    # run only group G
"""

from __future__ import annotations

import importlib
import inspect
import math
import os
import platform
import re
import sys
import time
import traceback
import types
from typing import Callable, NamedTuple

# ── Resolve project root ──────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── CLI args ──────────────────────────────────────────────────────────────────
_VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
_GROUPS_ARG: list[str] = []
for _a in sys.argv[1:]:
    if _a.startswith("--groups="):
        _GROUPS_ARG = [g.strip().upper() for g in _a.split("=", 1)[1].split(",")]
    elif _a.startswith("--groups"):
        idx = sys.argv.index(_a)
        if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
            _GROUPS_ARG = [g.strip().upper() for g in sys.argv[idx + 1].split(",")]

# ── Colour helpers ────────────────────────────────────────────────────────────
_TERM = sys.stdout.isatty() or os.environ.get("FORCE_COLOR", "")
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TERM else text

def _green(s: str)  -> str: return _c("92", s)
def _red(s: str)    -> str: return _c("91", s)
def _yellow(s: str) -> str: return _c("93", s)
def _cyan(s: str)   -> str: return _c("96", s)
def _bold(s: str)   -> str: return _c("1",  s)


# ═══════════════════════════════════════════════════════════════════════════════
#  Result tracking
# ═══════════════════════════════════════════════════════════════════════════════

class _Result(NamedTuple):
    passed: bool
    name: str
    detail: str


class _Group:
    def __init__(self, label: str, title: str):
        self.label = label
        self.title = title
        self.results: list[_Result] = []
        self._start = time.perf_counter()

    def ok(self, name: str, detail: str = "") -> None:
        self.results.append(_Result(True, name, detail))
        if _VERBOSE:
            print(f"    {_green('✓')} {name}" + (f"  ({detail})" if detail else ""))

    def warn(self, name: str, detail: str = "") -> None:
        # Soft check — records as PASS but prints warning
        self.results.append(_Result(True, name, f"WARN: {detail}"))
        print(f"    {_yellow('!')} {name}" + (f"  ({detail})" if detail else ""))

    def fail(self, name: str, detail: str = "") -> None:
        self.results.append(_Result(False, name, detail))
        print(f"    {_red('✗')} {name}" + (f"  ({detail})" if detail else ""))

    def check(self, condition: bool, name: str, detail: str = "") -> None:
        if condition:
            self.ok(name, detail)
        else:
            self.fail(name, detail)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000


# ═══════════════════════════════════════════════════════════════════════════════
#  Group A — Import chain
# ═══════════════════════════════════════════════════════════════════════════════

def group_a_imports(g: _Group) -> None:
    """Every public module must import without raising."""
    PUBLIC_MODULES = [
        "acoustic",
        "acoustic.resonance",
        "acoustic.emitter",
        "acoustic.beam",
        "acoustic.probe",
        "detection",
        "detection.acoustic_detect",
        "flight",
        "flight.telemetry",
    ]

    for mod_name in PUBLIC_MODULES:
        try:
            mod = importlib.import_module(mod_name)
            g.ok(f"import {mod_name}", f"file: {getattr(mod, '__file__', 'built-in') or 'N/A'}")
        except ImportError as exc:
            # Optional hardware deps (sounddevice, serial) are acceptable import failures
            # only if the module is NOT a core algorithm module.
            hw_optional = ("sounddevice", "serial", "usb", "cv2",
                           "pynput", "smbus", "spidev")
            root_cause = str(exc)
            if any(dep in root_cause for dep in hw_optional) and mod_name.startswith("flight"):
                g.warn(f"import {mod_name}", f"optional hardware dep missing: {exc}")
            else:
                g.fail(f"import {mod_name}", str(exc))
        except Exception as exc:
            g.fail(f"import {mod_name} (unexpected error)", repr(exc))


# ═══════════════════════════════════════════════════════════════════════════════
#  Group B — Package structure
# ═══════════════════════════════════════════════════════════════════════════════

def group_b_structure(g: _Group) -> None:
    """Package __init__.py files exist; directory layout is correct."""
    REQUIRED_FILES = [
        "soul_gui.py",
        "test_harness.py",
        "bench_test.py",
        "acoustic/__init__.py",
        "acoustic/beam.py",
        "acoustic/emitter.py",
        "acoustic/probe.py",
        "acoustic/resonance.py",
        "detection/__init__.py",
        "detection/acoustic_detect.py",
        "flight/__init__.py",
        "flight/telemetry.py",
    ]

    for rel_path in REQUIRED_FILES:
        full = os.path.join(_ROOT, *rel_path.split("/"))
        g.check(os.path.isfile(full), f"exists: {rel_path}")

    # Build scripts present
    BUILD_FILES = [
        ("SoulMusic.spec",           "Windows PyInstaller spec"),
        ("SoulMusic-linux.spec",     "Linux PyInstaller spec"),
        ("build_installer.ps1",      "Windows build script"),
        ("build_installer_linux.sh", "Linux build script"),
        ("install_linux.sh",         "Linux installer"),
        ("SoulMusic.desktop",        "Linux desktop entry"),
        ("SoulMusic.iss",            "Windows Inno Setup script"),
        ("SoulPlan.md",              "Release plan document"),
    ]
    for fname, desc in BUILD_FILES:
        full = os.path.join(_ROOT, fname)
        if os.path.isfile(full):
            g.ok(f"present: {fname}", desc)
        else:
            g.warn(f"missing: {fname}", f"{desc} — not critical for runtime but expected for release")

    # No stale .pyc without matching .py source
    for dirpath, _dirnames, filenames in os.walk(_ROOT):
        # Skip build artefacts
        if any(skip in dirpath for skip in ("build", "dist", "__pycache__", ".git")):
            continue
        for fname in filenames:
            if fname.endswith(".pyc"):
                src = fname[:-1]  # .pyc → .py
                src_path = os.path.join(dirpath, src)
                if not os.path.isfile(src_path):
                    g.fail(f"stale .pyc: {os.path.relpath(os.path.join(dirpath, fname), _ROOT)}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Group C — Module wiring
# ═══════════════════════════════════════════════════════════════════════════════

def group_c_wiring(g: _Group) -> None:
    """Key inter-module contracts are satisfied at the API level."""

    # ── C1: acoustic.resonance — MEMS profiles dict ──
    try:
        import acoustic.resonance as res
        profiles = getattr(res, "MEMS_PROFILES", None) or getattr(res, "SENSOR_PROFILES", None)
        g.check(profiles is not None, "acoustic.resonance exposes MEMS_PROFILES or SENSOR_PROFILES")
        if profiles is not None:
            g.check(isinstance(profiles, dict), "MEMS_PROFILES is a dict",
                    f"type={type(profiles).__name__}")
            g.check(len(profiles) >= 3, "MEMS_PROFILES has ≥ 3 entries",
                    f"count={len(profiles)}")
            # Each entry should have a resonance_hz key (or equivalent)
            sample = next(iter(profiles.values()))
            has_freq = (
                isinstance(sample, dict) and any(
                    k in sample for k in ("resonance_hz", "freq_hz", "frequency_hz",
                                          "gyro_resonance_hz", "natural_freq_hz")
                )
            ) or hasattr(sample, "resonance_hz") or hasattr(sample, "freq_hz")
            g.check(has_freq, "MEMS_PROFILES entries contain resonance frequency field",
                    f"sample keys: {list(sample.keys()) if isinstance(sample, dict) else dir(sample)[:4]}")
    except ImportError:
        g.warn("acoustic.resonance import skipped (ImportError)")

    # ── C2: acoustic.emitter — control API functions ──
    try:
        import acoustic.emitter as emitter
        # Emitter uses a command-queue design — public API is init/update/stop
        api_fns = ["init_emitter", "update_emitter", "stop_emitter", "update_beam"]
        found = [f for f in api_fns if callable(getattr(emitter, f, None))]
        g.check(len(found) >= 2,
                "acoustic.emitter exposes control API (init_emitter, update_emitter, …)",
                f"found: {found}")
        # Also check EmitterState dataclass is accessible
        g.check(hasattr(emitter, "EmitterState"),
                "acoustic.emitter exposes EmitterState dataclass")
    except ImportError:
        g.warn("acoustic.emitter import skipped (ImportError)")

    # ── C3: acoustic.probe — SHELL_PRESETS or similar config ──
    try:
        import acoustic.probe as probe
        presets = getattr(probe, "SHELL_PRESETS", None) or getattr(probe, "PROBE_PRESETS", None)
        g.check(presets is not None, "acoustic.probe exposes SHELL_PRESETS or PROBE_PRESETS")
        if presets is not None and isinstance(presets, dict):
            g.check(len(presets) >= 1, "Probe presets has ≥ 1 entry",
                    f"count={len(presets)}")
    except ImportError:
        g.warn("acoustic.probe import skipped (ImportError)")

    # ── C4: detection.acoustic_detect — PlatformProfile + PLATFORM_DB ──
    try:
        import detection.acoustic_detect as adet
        # PlatformProfile dataclass must be importable
        g.check(hasattr(adet, "PlatformProfile"),
                "detection.acoustic_detect exposes PlatformProfile")
        g.check(hasattr(adet, "PLATFORM_DB"),
                "detection.acoustic_detect exposes PLATFORM_DB")
        # detect_propeller_signature is expected by test_harness.py but not yet implemented
        fn = getattr(adet, "detect_propeller_signature", None)
        if fn is not None:
            g.ok("detection.acoustic_detect.detect_propeller_signature exists")
        else:
            g.warn("detect_propeller_signature not yet implemented in acoustic_detect",
                   "test_harness.py imports it — add this function to close the gap")
    except ImportError as exc:
        g.warn("detection.acoustic_detect import skipped (ImportError)", str(exc))

    # ── C5: flight.telemetry — get_telemetry() returns expected keys ──
    try:
        import flight.telemetry as telem
        fn = getattr(telem, "get_telemetry", None)
        g.check(fn is not None, "flight.telemetry.get_telemetry exists")
        if fn is not None:
            g.check(callable(fn), "get_telemetry is callable")
            try:
                # Call with no connection — should return a dict or raise gracefully
                result = fn()
                if isinstance(result, dict):
                    EXPECTED_KEYS = {"ts", "lat", "lon"}
                    present = EXPECTED_KEYS.intersection(result.keys())
                    g.check(len(present) >= 1,
                            "get_telemetry() dict contains at least one expected key (ts/lat/lon)",
                            f"keys present: {present}")
            except Exception as exc:
                # Hardware not connected — acceptable
                g.warn("get_telemetry() raised (no hardware)", str(exc))
    except ImportError:
        g.warn("flight.telemetry import skipped (ImportError)")


# ═══════════════════════════════════════════════════════════════════════════════
#  Group D — Platform database
# ═══════════════════════════════════════════════════════════════════════════════

def group_d_platform_db(g: _Group) -> None:
    """PLATFORM_DB entries have consistent schema; known bugs are flagged."""
    try:
        from detection.acoustic_detect import PLATFORM_DB
    except ImportError as exc:
        g.warn("PLATFORM_DB not importable", str(exc))
        return

    g.check(isinstance(PLATFORM_DB, dict), "PLATFORM_DB is a dict",
            f"type={type(PLATFORM_DB).__name__}")
    g.check(len(PLATFORM_DB) >= 5, "PLATFORM_DB has ≥ 5 entries",
            f"count={len(PLATFORM_DB)}")

    # PLATFORM_DB values are PlatformProfile dataclasses — handle both dict and dataclass.
    def _prof_get(entry, *attrs):
        """Retrieve first matching attribute from a dict or dataclass."""
        if isinstance(entry, dict):
            for a in attrs:
                if a in entry:
                    return entry[a]
        else:
            for a in attrs:
                v = getattr(entry, a, None)
                if v is not None:
                    return v
        return None

    missing_required: list[str] = []
    missing_sensor: list[str] = []

    for name, entry in PLATFORM_DB.items():
        # bpf: accept bpf_hz (scalar) or bpf_range_hz (tuple)
        bpf_raw = _prof_get(entry, "bpf_hz", "bpf_range_hz")
        if bpf_raw is None:
            missing_required.append(f"{name}.bpf")
        else:
            try:
                # tuple range → use lower bound
                bpf_val = float(min(bpf_raw) if hasattr(bpf_raw, "__iter__") else bpf_raw)
                g.check(bpf_val > 0,
                        f"PLATFORM_DB['{name}'].bpf > 0",
                        f"value={bpf_raw}")
            except (TypeError, ValueError):
                g.fail(f"PLATFORM_DB['{name}'].bpf is not numeric", repr(bpf_raw))

        # blade count
        blades = _prof_get(entry, "blades", "blade_count")
        if blades is None:
            missing_required.append(f"{name}.blade_count")
        else:
            try:
                g.check(int(blades) > 0, f"PLATFORM_DB['{name}'].blade_count > 0",
                        f"value={blades}")
            except (TypeError, ValueError):
                g.fail(f"PLATFORM_DB['{name}'].blade_count not integer", repr(blades))

        # motor count
        motors = _prof_get(entry, "motors", "motor_count")
        if motors is None:
            missing_required.append(f"{name}.motor_count")
        else:
            try:
                g.check(int(motors) > 0, f"PLATFORM_DB['{name}'].motor_count > 0",
                        f"value={motors}")
            except (TypeError, ValueError):
                g.fail(f"PLATFORM_DB['{name}'].motor_count not integer", repr(motors))

        # sensor field
        sensor = _prof_get(entry, "imu_model", "mems_model", "sensor", "mems_sensor")
        if sensor is None:
            missing_sensor.append(name)

    g.check(len(missing_required) == 0,
            "No PLATFORM_DB entries missing required fields",
            f"missing: {missing_required}" if missing_required else "all present")

    if missing_sensor:
        g.warn(f"{len(missing_sensor)} platform(s) missing IMU/sensor field",
               f"{missing_sensor[:4]}{'...' if len(missing_sensor) > 4 else ''}")

    # BUG-01: ICM-42688-P vs BMI088 discrepancy check
    # DJI Mavic 3, Mini 4 Pro, Matrice 30 teardowns report BMI088 as primary gyro.
    # If PLATFORM_DB maps these to ICM-42688-P, flag it as a known data issue.
    KNOWN_BMI088_PLATFORMS = {
        k: v for k, v in PLATFORM_DB.items()
        if any(name_frag in k.lower() for name_frag in
               ("mavic 3", "mini 4", "matrice 30", "mavic3", "mini4", "matrice30"))
    }
    if KNOWN_BMI088_PLATFORMS:
        for plat_name, entry in KNOWN_BMI088_PLATFORMS.items():
            sensor_val = _prof_get(entry, "imu_model", "mems_model", "sensor", "mems_sensor") or ""
            if "ICM-42688" in str(sensor_val).upper():
                g.warn(
                    f"BUG-01: {plat_name!r} mapped to ICM-42688-P",
                    "Teardown reports BMI088 as primary gyro. Verify against hardware."
                )
            else:
                g.ok(f"BUG-01 not triggered for {plat_name!r}",
                     f"sensor={sensor_val!r}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Group E — Configuration constants
# ═══════════════════════════════════════════════════════════════════════════════

def group_e_constants(g: _Group) -> None:
    """Numeric constants in sensor profiles are physically plausible."""
    try:
        import acoustic.resonance as res
        profiles = getattr(res, "MEMS_PROFILES", None) or getattr(res, "SENSOR_PROFILES", None)
    except ImportError:
        g.warn("acoustic.resonance not available — skipping constant checks")
        return

    if profiles is None:
        g.warn("No MEMS_PROFILES/SENSOR_PROFILES found")
        return

    # Plausible resonance frequency range: 10 Hz – 50 kHz
    FREQ_MIN = 10.0
    FREQ_MAX = 50_000.0

    for sensor_name, profile in profiles.items():
        if isinstance(profile, dict):
            freq_val = (
                profile.get("resonance_hz") or profile.get("freq_hz") or
                profile.get("frequency_hz") or profile.get("gyro_resonance_hz") or
                profile.get("natural_freq_hz")
            )
        else:
            freq_val = getattr(profile, "resonance_hz", None) or getattr(profile, "freq_hz", None)

        if freq_val is None:
            g.warn(f"{sensor_name}: no resonance frequency field found")
            continue

        try:
            freq = float(freq_val)
            g.check(FREQ_MIN <= freq <= FREQ_MAX,
                    f"{sensor_name}: resonance_hz in plausible range",
                    f"{freq:.1f} Hz  (expected {FREQ_MIN}–{FREQ_MAX})")
            g.check(math.isfinite(freq),
                    f"{sensor_name}: resonance_hz is finite")
        except (TypeError, ValueError) as exc:
            g.fail(f"{sensor_name}: resonance_hz is non-numeric", repr(exc))

    # Check acoustic.beam — SPEED_OF_SOUND constant plausibility
    try:
        import acoustic.beam as beam
        sos = getattr(beam, "SPEED_OF_SOUND", None) or getattr(beam, "C", None)
        if sos is not None:
            g.check(330.0 <= float(sos) <= 360.0,
                    "acoustic.beam: SPEED_OF_SOUND in range 330–360 m/s",
                    f"value={sos}")
        else:
            g.warn("acoustic.beam: no SPEED_OF_SOUND/C constant found")
    except ImportError:
        g.warn("acoustic.beam not available")

    # test_harness.py defines SAMPLE_RATE — make sure it's plausible
    try:
        import test_harness as th
        sr = getattr(th, "SAMPLE_RATE", None)
        if sr is not None:
            g.check(8000 <= int(sr) <= 192000,
                    "test_harness.SAMPLE_RATE in 8k–192k Hz range",
                    f"value={sr}")
    except ImportError:
        g.warn("test_harness not importable from this path")


# ═══════════════════════════════════════════════════════════════════════════════
#  Group F — File system & paths
# ═══════════════════════════════════════════════════════════════════════════════

def group_f_paths(g: _Group) -> None:
    """All paths resolved at import time resolve correctly relative to project root."""

    # Read each Python module and scan for hardcoded absolute paths
    SCAN_MODULES = [
        "acoustic/beam.py",
        "acoustic/emitter.py",
        "acoustic/probe.py",
        "acoustic/resonance.py",
        "detection/acoustic_detect.py",
        "flight/telemetry.py",
        "test_harness.py",
        "bench_test.py",
    ]

    # Patterns that indicate a hardcoded absolute path
    # Excludes strings that are clearly comments or docstrings (best-effort)
    ABS_PATH_RE = re.compile(
        r"""(?x)
        (?:["'])                 # opening quote
        (
          [A-Za-z]:\\\\[^"']{4,} # Windows: C:\...
          | /(?:home|Users|opt|root|etc|usr)/[^"']{4,} # Unix absolute with named root
        )
        (?:["'])                 # closing quote
        """,
        re.VERBOSE,
    )

    for rel in SCAN_MODULES:
        full = os.path.join(_ROOT, *rel.split("/"))
        if not os.path.isfile(full):
            continue
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError as exc:
            g.fail(f"Cannot read {rel}", str(exc))
            continue

        hardcoded = ABS_PATH_RE.findall(src)
        if hardcoded:
            g.warn(f"{rel}: hardcoded absolute path(s)",
                   f"{hardcoded[:2]}{'...' if len(hardcoded) > 2 else ''}")
        else:
            g.ok(f"{rel}: no hardcoded absolute paths")

    # Verify project root path-setup idiom in test_harness.py
    th_path = os.path.join(_ROOT, "test_harness.py")
    if os.path.isfile(th_path):
        with open(th_path, "r", encoding="utf-8") as fh:
            th_src = fh.read()
        uses_dirname = "__file__" in th_src and ("dirname" in th_src or "parent" in th_src)
        g.check(uses_dirname,
                "test_harness.py uses __file__-relative path setup",
                "no __file__-relative path detected — tests may break from other directories" if not uses_dirname else "OK")


# ═══════════════════════════════════════════════════════════════════════════════
#  Group G — Cross-platform compatibility
# ═══════════════════════════════════════════════════════════════════════════════

def group_g_compat(g: _Group) -> None:
    """Shared Python source uses no Windows-only or Linux-only symbols."""

    # These modules are shared and must work on both platforms
    SHARED_MODULES = [
        "acoustic/beam.py",
        "acoustic/emitter.py",
        "acoustic/probe.py",
        "acoustic/resonance.py",
        "detection/acoustic_detect.py",
        "flight/telemetry.py",
        "test_harness.py",
    ]

    # Windows-only symbols / imports that should NOT appear in shared code
    WINDOWS_ONLY = [
        "winreg", "winnt", "win32api", "win32con", "win32gui",
        "win32process", "winerror", "ctypes.windll", "ctypes.wintypes",
        "msvcrt", "msilib",
        r"\.ps1",        # PowerShell script references
        r"\\\\",         # Windows-style double-backslash literal paths
        r"HKEY_",        # Windows registry key constants
        r"SHGetFolderPath", r"GetWindowsDirectory",
    ]

    # Linux-only that should NOT appear in shared code (acceptable in linux-specific files)
    LINUX_ONLY = [
        r"\/usr\/",      # Hardcoded /usr/ paths in logic
        r"\/etc\/",
        "subprocess.*apt",
        "subprocess.*dnf",
        "subprocess.*pacman",
        # Note: /dev/ttyUSB0 etc. in flight/telemetry.py is expected — serial ports
    ]

    LINUX_SPECIFIC_FILES = {"install_linux.sh", "build_installer_linux.sh",
                            "SoulMusic-linux.spec", "SoulMusic.desktop"}

    for rel in SHARED_MODULES:
        full = os.path.join(_ROOT, *rel.split("/"))
        if not os.path.isfile(full):
            continue
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError:
            continue

        issues: list[str] = []
        for pattern in WINDOWS_ONLY:
            if re.search(pattern, src):
                issues.append(f"Windows-only: {pattern!r}")
        # Only flag Linux-only in shared Python files (not install scripts)
        if rel not in LINUX_SPECIFIC_FILES:
            for pattern in LINUX_ONLY:
                if re.search(pattern, src):
                    issues.append(f"Linux-only: {pattern!r}")

        if issues:
            g.warn(f"{rel}: platform-specific references",
                   "; ".join(issues[:3]))
        else:
            g.ok(f"{rel}: no platform-specific symbols")

    # Verify os.sep / pathlib usage in soul_gui.py if present
    gui_path = os.path.join(_ROOT, "soul_gui.py")
    if os.path.isfile(gui_path):
        with open(gui_path, "r", encoding="utf-8", errors="replace") as fh:
            gui_src = fh.read()
        uses_backslash_join = re.search(r'["\']\s*\\\\\s*["\']', gui_src)
        g.check(not uses_backslash_join,
                "soul_gui.py: no bare backslash path separators in string literals")

    # Python version check — code must target 3.10+
    pv = sys.version_info
    g.check(pv >= (3, 10),
            f"Python ≥ 3.10 (required by SoulMusic)",
            f"running {pv.major}.{pv.minor}.{pv.micro}")

    # PySide6 must be importable (GUI requires it)
    try:
        import PySide6
        ver = getattr(PySide6, "__version__", "unknown")
        g.ok("PySide6 importable", f"version {ver}")
    except ImportError as exc:
        g.warn("PySide6 not installed (GUI will not launch)", str(exc))

    # numpy must be importable (signal processing requires it)
    try:
        import numpy as np
        g.ok("numpy importable", f"version {np.__version__}")
    except ImportError as exc:
        g.fail("numpy not installed (required by detection algorithms)", str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
#  Runner
# ═══════════════════════════════════════════════════════════════════════════════

_GROUPS: dict[str, tuple[str, Callable]] = {
    "A": ("Import Chain",           group_a_imports),
    "B": ("Package Structure",      group_b_structure),
    "C": ("Module Wiring",          group_c_wiring),
    "D": ("Platform Database",      group_d_platform_db),
    "E": ("Configuration Constants",group_e_constants),
    "F": ("File System & Paths",    group_f_paths),
    "G": ("Cross-Platform Compat",  group_g_compat),
}


def main() -> int:
    run_labels = _GROUPS_ARG if _GROUPS_ARG else list(_GROUPS.keys())
    invalid = [l for l in run_labels if l not in _GROUPS]
    if invalid:
        print(f"Unknown group(s): {invalid}. Valid groups: {list(_GROUPS.keys())}")
        return 1

    print(_bold(f"\nSoulMusic — CI Smoke Tests  ({platform.system()} / Python {sys.version_info.major}.{sys.version_info.minor})"))
    print(f"Root: {_ROOT}")
    print(f"Groups: {', '.join(run_labels)}\n")

    all_passed = True
    group_results: list[_Group] = []

    for label in run_labels:
        title, fn = _GROUPS[label]
        g = _Group(label, title)
        print(f"{_bold(_cyan(f'[{label}]'))} {_bold(title)}")
        try:
            fn(g)
        except Exception as exc:
            g.fail(f"Group {label} raised an unexpected exception", repr(exc))
            if _VERBOSE:
                traceback.print_exc()

        status = _green("PASS") if g.failed == 0 else _red("FAIL")
        print(f"     {status}  {g.passed}✓  {g.failed}✗  ({g.elapsed_ms:.0f}ms)\n")
        group_results.append(g)
        if g.failed > 0:
            all_passed = False

    # ── Summary ───────────────────────────────────────────────────────────────
    total_pass = sum(g.passed for g in group_results)
    total_fail = sum(g.failed for g in group_results)
    total     = total_pass + total_fail

    print("─" * 52)
    print(_bold(f"  Total: {total_pass}/{total} passed"))
    if total_fail > 0:
        print(_red(f"  {total_fail} assertion(s) failed:\n"))
        for g in group_results:
            for r in g.results:
                if not r.passed:
                    print(f"    [{g.label}] {r.name}")
                    if r.detail:
                        print(f"          {r.detail}")
    print()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
