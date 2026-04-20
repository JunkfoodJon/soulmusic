<div align="center">

<h1>🎵 SoulMusic</h1>

<p>
  <img src="https://img.shields.io/badge/OPEN%20SOURCE-%C2%B7%20FREE%20TO%20BUILD%20%C2%B7%20USA%20LEGAL-1a2233?style=for-the-badge&labelColor=1a2233&color=2d4a6e" alt="Open Source · Free to Build · USA Legal" />
</p>

<h2><strong>Hostile drones cost $300.</strong><br>So does stopping them.</h2>

<p>An open-source acoustic counter-drone system anyone can build from off-the-shelf parts.<br>
Protection shouldn't only belong to people with defense budgets.</p>

<p>
  <a href="#quick-start"><img src="https://img.shields.io/badge/See%20the%20Overview-2563EB?style=for-the-badge" alt="See the Overview" /></a>
  <br>
  <a href="https://github.com/JunkfoodJon/soulmusic"><img src="https://img.shields.io/badge/View%20on%20GitHub-24292e?style=for-the-badge&logo=github&logoColor=white" alt="View on GitHub" /></a>
</p>

<br>

<table>
<tr>
<td align="center">✅&nbsp; <strong>Total build cost: ~$300</strong> &nbsp;·&nbsp; No special licenses required</td>
</tr>
</table>

<br>

<div align="center">

[![License: SEUL v2.0](https://img.shields.io/badge/license-SEUL%20v2.0-blue.svg)](LICENSE)
[![Python ≥ 3.10](https://img.shields.io/badge/python-%E2%89%A53.10-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4?logo=windows&logoColor=white)](SoulMusic-Open/build_installer.ps1)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-FCC624?logo=linux&logoColor=black)](SoulMusic-Open/install_linux.sh)

</div>

</div>

---

> **⚠️ USE AT YOUR OWN RISK.** This software is provided as-is, without warranty of any kind.
> It has not been validated on all hardware configurations. Verify your local laws before
> any operational deployment. See [Disclaimer](#disclaimer) below.

---

SoulMusic is an open-source **acoustic counter-UAS (Uncrewed Aerial System)** research
platform. It exploits MEMS gyroscope resonance physics to detect and characterise drones
using a ~$300 hardware setup. The dashboard provides real-time signal analysis,
beamforming visualisation, platform identification, and waveform generation — all
without RF emissions.

---

## 📋 Table of Contents

1. [📸 Screenshots](#-screenshots)
2. [⚡ Quick Start](#-quick-start)
3. [📦 Requirements](#-requirements)
4. [🖥️ Platform Support](#️-platform-support)
5. [🛠️ Installation](#️-installation)
   - [Windows](#windows)
   - [Linux](#linux)
   - [Troubleshooting](#troubleshooting)
6. [🎛️ Usage](#️-usage)
7. [🔧 Hardware Overview & Wiring](#-hardware-overview--wiring)
8. [📁 Project Structure](#-project-structure)
9. [🧪 Running Tests](#-running-tests)
10. [🔌 Plugin API](#-plugin-api)
11. [🤝 Contributing](#-contributing)
12. [⚠️ Known Issues](#️-known-issues)
13. [📄 License](#-license)
14. [🚨 Disclaimer](#-disclaimer)

---

## 📸 Screenshots

> 📸 **Screenshots wanted!** See [`docs/screenshots/README.md`](docs/screenshots/README.md)
> for capture guidelines and how to contribute.

<!-- Once screenshots are available, uncomment and update these lines:
![SoulMusic dashboard overview](docs/screenshots/dashboard-overview.png)
![Signal Analysis tab](docs/screenshots/tab-signal-analysis.png)
![Beamforming Visualisation tab](docs/screenshots/tab-beamforming.png)
![Platform Identification tab](docs/screenshots/tab-platform-id.png)
![Emitter / Waveform Generation tab](docs/screenshots/tab-emitter.png)
![Module Loader tab](docs/screenshots/tab-module-loader.png)
-->

---

## ⚡ Quick Start

```bash
# Python 3.10+ and pip required
pip install PySide6 numpy

# Optional — serial port and live audio capture:
pip install pyserial sounddevice matplotlib

# Launch the GUI
cd SoulMusic-Open
python soul_gui.py
```

---

## 📦 Requirements

| Package      | Version  | Required? | Purpose                       |
|--------------|----------|-----------|-------------------------------|
| Python       | ≥ 3.10   | Yes       | Runtime                       |
| PySide6      | ≥ 6.5    | Yes       | GUI framework                 |
| numpy        | ≥ 1.24   | Yes       | Signal processing             |
| pyserial     | ≥ 3.5    | Optional  | Arduino / MCU communication   |
| sounddevice  | ≥ 0.4    | Optional  | Live microphone capture       |
| matplotlib   | ≥ 3.7    | Optional  | Waveform plots                |

Full dependency list: [`SoulMusic-Open/requirements.txt`](SoulMusic-Open/requirements.txt) (runtime).
Optional extras (`pyserial`, `sounddevice`, `matplotlib`) can be installed individually as shown above.

---

## 🖥️ Platform Support

| Platform            | Status       | Notes                                  |
|---------------------|--------------|----------------------------------------|
| Windows 10/11 x64   | ✅ Primary   | GUI + PyInstaller build tested         |
| Ubuntu 20.04 LTS    | ✅ Supported | Run-from-source; AppImage planned      |
| Ubuntu 22.04 LTS    | ✅ Supported | Run-from-source; AppImage planned      |
| Ubuntu 24.04 LTS    | ✅ Supported | Run-from-source                        |
| Debian 11/12        | ✅ Supported | Run-from-source                        |
| Fedora 38/39        | ✅ Supported | Run-from-source                        |
| Raspberry Pi OS     | ⚠️ Best-effort | ARM; PySide6 availability varies    |
| macOS 13+           | ⚠️ Best-effort | Not actively tested; may work       |

---

## 🛠️ Installation

### Windows

**Option A — Pre-built installer (recommended)**

1. Download `SoulMusic-Setup-1.0.0.exe` from the [Releases](../../releases) page.
2. Run the installer and follow the prompts.
3. Launch from **Start Menu → SoulMusic**.

**Option B — Build from source**

```powershell
cd SoulMusic-Open
.\build_installer.ps1
```

The installer will be placed in `SoulMusic-Open\dist\`.

---

### Linux

**Option A — Install script**

```bash
cd SoulMusic-Open

# System-wide install (recommended, requires sudo)
sudo bash install_linux.sh

# Per-user install (no sudo required)
bash install_linux.sh --user
```

**Option B — Build a self-contained bundle**

```bash
cd SoulMusic-Open
bash build_installer_linux.sh
./dist/SoulMusic/SoulMusic
```

**Option C — Run directly from source**

```bash
cd SoulMusic-Open
pip install -r requirements.txt
python soul_gui.py
```

---

### Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: PySide6` | PySide6 not installed | `pip install PySide6` |
| No serial ports visible | `pyserial` not installed or device not connected | `pip install pyserial`; check USB cable |
| Audio interface not detected | `sounddevice` not installed or driver missing | `pip install sounddevice`; reinstall audio drivers |
| GUI blank / black screen | Outdated GPU drivers (OpenGL) | Update drivers; try `QT_OPENGL=software python soul_gui.py` |
| `PermissionError` on `/dev/ttyUSB*` | User not in `dialout` group | `sudo usermod -aG dialout $USER`, then re-login |

---

## 🎛️ Usage

### Launching the GUI

```bash
cd SoulMusic-Open
python soul_gui.py
```

On Windows you can also double-click `SoulMusic.exe` from the installed location.

### Dashboard Tabs

The GUI is organised into nine tabs:

| Tab | Description |
|-----|-------------|
| **Signal Analysis** | Real-time FFT of mic/audio input; peak detection and frequency annotation |
| **Beamforming** | Phased-array delay-and-sum visualisation; steer the receive beam across azimuth/elevation |
| **Platform ID** | Passive Doppler detection; matches blade-pass frequency signatures to `PLATFORM_DB` |
| **Emitter** | Waveform generator; configure sweep range, burst duration, Doppler pre-compensation, and output device |
| **Probe** | Active hardware characterisation; pings the connected MEMS sensor and analyses the reflection |
| **Bench Test** | Step-by-step guided bench test wrapping `bench_test.py` with a progress view |
| **Telemetry** | MAVLink feed (optional); live position, altitude, and IMU data from a flight controller |
| **Module Loader** | Drop-in Python plugin registry; load custom calculation modules at runtime (see [Plugin API](#plugin-api)) |
| **Settings** | Audio device, serial port, sample rate, and theme |

---

## 🔧 Hardware Overview & Wiring

> **Research and educational use only.** High-level descriptions are provided here.
> For full schematics, see:
> - [`SoulMusic-Open/docs/hardware-bom.md`](SoulMusic-Open/docs/hardware-bom.md) — component list with sourcing notes
> - [`SoulMusic-Open/docs/wiring-diagram.md`](SoulMusic-Open/docs/wiring-diagram.md) — full ASCII schematics
> - [`SoulMusic-Open/ARCHITECTURE.md`](SoulMusic-Open/ARCHITECTURE.md) — system architecture and scientific basis

### Minimum Bench Rig

> 💰 **~$45–$110 USD** excluding host computer

| # | Component | Role |
|---|-----------|------|
| 1 | MEMS gyroscope breakout (e.g. MPU-6050, BMI270) | Test-subject sensor |
| 2 | Ultrasonic transducer (25–40 kHz piezo) | Acoustic emission |
| 3 | Class-D amplifier board (≥10 W) | Drive the transducer |
| 4 | USB audio interface (≥96 kHz, 24-bit) | High-bandwidth signal output + capture |
| 5 | Arduino-compatible microcontroller | Read MEMS gyro over I²C → serial to host |
| 6 | Host computer | Run `soul_gui.py` |

### High-Level Connection Overview

```
Host PC
  │
  ├─ USB ──→ USB Audio Interface ──→ Class-D Amp ──→ Ultrasonic Transducer
  │                                                         ↕ (sound waves)
  │                                                  MEMS Sensor (test subject)
  │
  └─ USB ──→ Arduino (serial 115200) ←─ I²C ←─ MEMS Breakout Board
```

> See [`SoulMusic-Open/docs/wiring-diagram.md`](SoulMusic-Open/docs/wiring-diagram.md)
> for detailed per-pin ASCII schematics covering bench test, field emitter-only,
> and Raspberry Pi GPIO (I²S) configurations.

---

## 📁 Project Structure

```
soulmusic/
├── README.md                        ← You are here
├── LICENSE                          ← SEUL v2.0
├── docs/
│   └── screenshots/                 ← GUI screenshots (see README inside)
└── SoulMusic-Open/                  ← Source code and build scripts
    ├── soul_gui.py                  # Main GUI application (9 tabs)
    ├── acoustic/                    # Signal processing algorithms
    │   ├── beam.py                  # Beamforming calculations
    │   ├── emitter.py               # Waveform generation
    │   ├── probe.py                 # Hardware probe profiles
    │   └── resonance.py             # MEMS resonance profiles + MEMS_PROFILES DB
    ├── detection/
    │   └── acoustic_detect.py       # Platform detection, PLATFORM_DB
    ├── flight/
    │   └── telemetry.py             # MAVLink telemetry (optional)
    ├── docs/
    │   ├── hardware-bom.md          # Full component list + sourcing notes
    │   ├── wiring-diagram.md        # ASCII wiring schematics (3 configs)
    │   └── plugin-api.md            # Plugin API reference
    ├── test_harness.py              # Software-only accuracy tests
    ├── bench_test.py                # Hardware bench tests (requires rig)
    ├── ci_smoke_test.py             # CI integration / wiring tests
    ├── ARCHITECTURE.md              # System architecture + scientific basis
    ├── CHANGELOG.md                 # Release history
    ├── requirements.txt             # Runtime dependencies
    ├── SoulMusic.spec               # PyInstaller spec (Windows)
    ├── SoulMusic-linux.spec         # PyInstaller spec (Linux)
    ├── SoulMusic.iss                # Inno Setup installer script (Windows)
    ├── SoulMusic.desktop            # .desktop entry (Linux)
    ├── build_installer.ps1          # Windows build driver (PowerShell)
    ├── install_linux.sh             # Linux install script
    └── build_installer_linux.sh     # Linux build driver (Bash)
```

---

## 🧪 Running Tests

All test scripts live in `SoulMusic-Open/`. Run from that directory:

```bash
cd SoulMusic-Open

# Algorithmic accuracy tests — no hardware needed
python test_harness.py

# CI smoke tests — import chain, module wiring, compatibility
python ci_smoke_test.py

# Verbose output for all test groups
python ci_smoke_test.py --verbose

# Run a single test group (replace G with a group name)
python ci_smoke_test.py --groups=G

# Hardware bench tests — requires transducer rig + Arduino
python bench_test.py --help
```

---

## 🔌 Plugin API

SoulMusic's **Module Loader** tab supports drop-in Python plugins. Any `.py` file
placed in a `plugins/` directory inside `SoulMusic-Open/` is auto-discovered at
startup or on demand via the **SCAN plugins/** button in the GUI.

### Minimal Plugin Example

```python
# SoulMusic-Open/plugins/my_plugin.py

SOUL_VERSION     = "1.0"
SOUL_DESCRIPTION = "My custom calculations"

def my_formula(freq_hz: float, range_m: float) -> dict:
    """Scale frequency by inverse-sqrt of range."""
    return {"result": freq_hz / (range_m ** 0.5), "units": "Hz/sqrt(m)"}

SOUL_CALCULATIONS = [
    {
        "name":        "My Formula",
        "fn":          my_formula,
        "description": "Scales frequency by inverse sqrt of range",
        "category":    "Acoustics",
        "params": [
            {
                "name":        "freq_hz",
                "type":        "float",
                "default":     25000.0,
                "description": "MEMS resonance in Hz",
            },
            {
                "name":        "range_m",
                "type":        "float",
                "default":     10.0,
                "min":         0.1,
                "max":         300.0,
                "description": "Target range in metres",
            },
        ],
    }
]
```

Each entry in `SOUL_CALCULATIONS` generates an interactive card in the UI.
The `fn` callable is dispatched in a background thread so the interface stays
responsive.

If `SOUL_CALCULATIONS` is absent, the loader auto-introspects all public
callables using Python type hints (lower-fidelity, no descriptions or bounds).

> 📄 Full API reference: [`SoulMusic-Open/docs/plugin-api.md`](SoulMusic-Open/docs/plugin-api.md)

---

## 🤝 Contributing

Contributions are welcome — bug reports, documentation improvements, new platform
profiles, and plugin examples are all appreciated.

### Development Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/<your-username>/soulmusic.git
cd soulmusic/SoulMusic-Open

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows PowerShell

# 3. Install runtime + dev dependencies
pip install -r requirements.txt
pip install pyserial sounddevice matplotlib   # optional extras

# 4. Run the smoke tests to verify your environment
python ci_smoke_test.py --verbose

# 5. Launch the GUI
python soul_gui.py
```

### Pull Request Guidelines

- Keep changes focused; one logical change per PR.
- Run `python ci_smoke_test.py` and `python test_harness.py` before submitting.
- For new MEMS sensor profiles, include a citation or bench-test data source.
- Documentation-only changes are welcome without test requirements.
- All contributions must comply with the [SoulMusic Ethical Use License](LICENSE).

---

## ⚠️ Known Issues

| ID       | Severity | Description |
|----------|----------|-------------|
| BUG-01   | High     | `PLATFORM_DB` maps DJI Mavic 3 / Mini 4 / Matrice 30 → ICM-42688-P, but teardown reports suggest BMI088 as primary gyro. Verify with `bench_test.py --sweep` on a physical unit before targeting these platforms. |
| INFO-01  | Low      | `ARCHITECTURE.md` references an older module count. Authoritative count is in `soul_gui.py`. |

---

## 📄 License

**SoulMusic Ethical Use License (SEUL) v2.0**

See [`LICENSE`](LICENSE) for the full text.

Copyright (c) 2024–2026 SoulMusic Contributors.

| | |
|---|---|
| ✅ | Personal, educational, research, and commercial use permitted |
| ✅ | Modification and redistribution permitted with attribution |
| ❌ | Use that causes physical harm to any person is **absolutely prohibited** (Clause C) |

---

## 🚨 Disclaimer

> **This software is experimental and provided WITHOUT ANY WARRANTY. It has not been
> validated in the field. ALL bench tests use synthetic audio signals — real-world
> performance will vary.**
>
> Counter-UAS technology is **regulated by law in most jurisdictions.** Using hardware
> or software to interfere with, track, or disable unmanned aircraft without proper
> authority may be a criminal offence. The authors accept NO LIABILITY for any damages,
> legal consequences, or loss arising from use or misuse of this software.
>
> **Verify your legal authority with a qualified attorney before any operational use.**
