# SoulMusic — Release README

> **USE AT YOUR OWN RISK. This software is provided as-is, without warranty of any kind.
> It has not been validated on all hardware configurations. Verify your local laws before
> any operational deployment. See [DISCLAIMER](#disclaimer) below.**

---

## What Is SoulMusic?

SoulMusic is an open-source acoustic counter-UAS (Uncrewed Aerial System) platform that
exploits MEMS gyroscope resonance physics to detect and characterise drones using a $300
hardware setup. The dashboard provides real-time signal analysis, beamforming visualisation,
platform identification, and waveform generation — all without RF emissions.

---

## Quick Start (Run From Source)

```bash
# Requirements: Python 3.10+, pip
pip install PySide6 numpy

# Optional (serial port + audio capture):
pip install pyserial sounddevice matplotlib

# Run
python soul_gui.py
```

---

## Requirements

| Package      | Version | Required? | Purpose                          |
|-------------|---------|-----------|----------------------------------|
| Python      | ≥ 3.10  | Yes       | Runtime                          |
| PySide6     | ≥ 6.5   | Yes       | GUI                              |
| numpy       | ≥ 1.24  | Yes       | Signal processing                |
| pyserial    | ≥ 3.5   | Optional  | Arduino/MCU communication        |
| sounddevice | ≥ 0.4   | Optional  | Live microphone capture          |
| matplotlib  | ≥ 3.7   | Optional  | Waveform plots                   |

Full dependency list: `requirements.txt` (runtime), `requirements-optional.txt` (extras).

---

## Platform Support

| Platform             | Status     | Notes                               |
|---------------------|------------|-------------------------------------|
| Windows 10/11 x64   | Primary    | GUI + PyInstaller build tested      |
| Ubuntu 20.04 LTS    | Supported  | Run-from-source; AppImage planned   |
| Ubuntu 22.04 LTS    | Supported  | Run-from-source; AppImage planned   |
| Ubuntu 24.04 LTS    | Supported  | Run-from-source                     |
| Debian 11/12        | Supported  | Run-from-source                     |
| Fedora 38/39        | Supported  | Run-from-source                     |
| Raspberry Pi OS     | Best-effort| ARM; PySide6 availability varies    |
| macOS 13+           | Best-effort| Not actively tested; may work       |

---

## Installation

### Windows
1. Download `SoulMusic-Setup-1.0.0.exe` from the release page.
2. Run the installer.
3. Launch from Start Menu → SoulMusic.

Or build from source:
```powershell
.\build_installer.ps1
```

### Linux
```bash
# System install (recommended — requires sudo)
sudo bash install_linux.sh

# User install (no sudo)
bash install_linux.sh --user

# Or build a self-contained bundle:
bash build_installer_linux.sh
./dist/SoulMusic/SoulMusic
```

---

## Project Structure

```
SoulMusic/
├── soul_gui.py                # Main GUI application (9 tabs)
├── acoustic/                  # Signal processing algorithms
│   ├── beam.py                # Beamforming calculations
│   ├── emitter.py             # Waveform generation
│   ├── probe.py               # Hardware probe profiles
│   └── resonance.py           # MEMS resonance profiles (8 sensors)
├── detection/
│   └── acoustic_detect.py     # Platform detection, PLATFORM_DB
├── flight/
│   └── telemetry.py           # MAVLink telemetry (optional)
├── test_harness.py            # Software-only accuracy tests
├── bench_test.py              # Hardware bench tests (requires rig)
├── ci_smoke_test.py           # CI integration/wiring tests
├── release/                   # This folder
│   ├── README.md              # ← You are here
│   ├── CHANGELOG.md
│   ├── MANIFEST.md
│   ├── LICENSE
│   ├── requirements.txt
│   ├── requirements-optional.txt
│   └── build/
│       ├── windows/           # Windows build artefacts
│       └── linux/             # Linux build artefacts
├── SoulMusic-index.html       # Project website
├── SoulMusic.spec             # PyInstaller spec (Windows)
├── SoulMusic-linux.spec       # PyInstaller spec (Linux)
├── SoulMusic.iss              # Inno Setup installer (Windows)
├── SoulMusic.desktop          # .desktop entry (Linux)
├── build_installer.ps1        # Windows build driver (PowerShell)
└── build_installer_linux.sh   # Linux build driver (Bash)
```

---

## Running Tests

```bash
# Algorithmic accuracy tests (no hardware needed)
python test_harness.py

# CI smoke tests — import chain, wiring, compatibility
python ci_smoke_test.py

# All groups verbose
python ci_smoke_test.py --verbose

# Single group
python ci_smoke_test.py --groups=G

# Hardware bench tests (requires transducer rig + Arduino)
python bench_test.py --help
```

---

## Known Issues

| ID      | Severity | Description                                                      |
|---------|----------|------------------------------------------------------------------|
| BUG-01  | High     | `PLATFORM_DB` maps DJI Mavic 3/Mini 4/Matrice 30 → ICM-42688-P. Teardown reports BMI088 as primary gyro. Verify hardware before targeting these platforms. |
| INFO-01 | Low      | `ARCHITECTURE.md` references an older module count. Authoritative count is in `soul_gui.py`. |

---

## Hardware Bill of Materials

See [HomeworkCores.md](../HomeworkCores.md) and [ARCHITECTURE.md](../ARCHITECTURE.md)
for the full hardware BOM including the acoustic emitter rig and Arduino interface.

**Minimum bench rig:** ~$300 USD (2024 pricing)

---

## Plugin API

SoulMusic v1.1 includes a Module Loader tab with a plugin registry. Third-party plugins
can be loaded at runtime via the GUI.

Plugin contract: any `.py` file dropped in the `plugins/` directory that exposes a
`PLUGIN_META` dict and a `run(context)` function will be auto-discovered.

```python
# plugins/my_plugin.py
PLUGIN_META = {
    "name":    "My Plugin",
    "version": "1.0.0",
    "author":  "You",
    "description": "What this plugin does.",
}

def run(context: dict) -> None:
    # context keys: "sample_rate", "audio_callback", "platform_db"
    pass
```

---

## License
SoulMusic Ethical Use License (SEUL) v2.0
See [LICENSE](LICENSE).

Copyright (c) 2024 SoulMusic Contributors.

---

## Disclaimer

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
