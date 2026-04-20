# SoulMusic — CHANGELOG

All notable changes to SoulMusic are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **Linux build infrastructure**: `SoulMusic-linux.spec` (PyInstaller ELF),
  `build_installer_linux.sh` (bash build driver), `install_linux.sh` (system/user
  installer with root-vs-user detection), `SoulMusic.desktop` (freedesktop.org entry).
- **HTML download page**: Disclaimer section ("use at your own risk"), updated release
  text removing stale Q3 2025 estimate, added separate Windows / Linux / Source buttons.
- **`ci_smoke_test.py`**: 7-group CI smoke test suite covering import chain, package
  structure, module wiring, PLATFORM_DB schema validation, constant plausibility,
  file-system path checks, and cross-platform compatibility audit.
- **`release/` folder**: `README.md`, `requirements.txt`, `requirements-optional.txt`,
  `CHANGELOG.md`, `MANIFEST.md`, `LICENSE` (MIT), `release/build/windows/`,
  `release/build/linux/`.
- **`SoulPlan.md`**: Full 5-track release readiness plan document.
- Meta description tag added to `SoulMusic-index.html`.

### Changed
- Download tab: single "DOWNLOAD SOURCE — COMING SOON" button split into three
  separate stubs (Windows / Linux / Source) with distinct icons.
- Download tab: `"Estimated: Q3 2025"` replaced with `"Release pending final bench
  validation. Run from source now — see the Setup tab."`.

---

## [1.1.0] — GUI Redesign

### Added
- **GETTING STARTED tab** (first position): Copyable code blocks, system check worker,
  step-by-step setup guide.
- **MODULE LOADER tab**: `ModuleRegistry` singleton, plugin auto-discovery from
  `plugins/` directory, `CalcWorker` background execution, parameter editor UI.
- **SYSTEM INFO tab**: `SysCheckWorker` gathers Python version, PySide6 version,
  numpy status, audio device list, serial port list, platform string.
- Helper classes: `CopyableCodeBlock`, `TutorialTab`, `ParamSpec`, `CalculationDef`,
  `PluginEntry`.
- Version label updated to `"Dashboard  v1.1  |  9 tabs"`.
- Status bar updated to `"Tests: 10  ·  Tabs: 9"`.

---

## [1.0.0] — Initial Release

### Added
- Core detection pipeline: propeller signature detection, Doppler speed measurement,
  platform identification, MEMS resonance attack resolution.
- `acoustic/` package: `beam.py`, `emitter.py`, `probe.py`, `resonance.py`.
- `detection/acoustic_detect.py` with `PLATFORM_DB`.
- `flight/telemetry.py` MAVLink telemetry bridge.
- `test_harness.py` — 10 software-only accuracy tests, ~120 assertions.
- `bench_test.py` — hardware bench tests (requires transducer rig).
- `SoulMusic-index.html` — 7-tab project website.
- `SoulMusic.spec` — Windows PyInstaller build.
- `SoulMusic.iss` — Windows Inno Setup installer.
- `build_installer.ps1` — PowerShell build driver.
- GUI `soul_gui.py` — initial 6 tabs: TEST SUITE, RESONANCE, BEAMFORMING, PLATFORMS,
  WAVEFORMS, TROPHY WALL.
