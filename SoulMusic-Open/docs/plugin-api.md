# SoulMusic Plugin API Reference

> **MODULE LOADER** — writing calculation plugins for SoulMusic

---

## Overview

SoulMusic's MODULE LOADER tab supports drop-in Python plugins. Any `.py` file
placed in the `plugins/` directory is auto-discovered at startup or on demand
via the **SCAN plugins/** button.

Plugins expose one or more *calculation entries* that appear as interactive
cards in the MODULE LOADER UI. Each card auto-generates an input form from
the entry's parameter metadata and runs the function when you click **RUN**.

---

## Minimum Plugin Structure

```python
# plugins/my_plugin.py

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

---

## `SOUL_CALCULATIONS` Schema

`SOUL_CALCULATIONS` is a **list of dicts**. Each dict defines one calculation
card in the UI.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | `str` | Yes | Card title displayed in the UI |
| `fn` | `callable` | Yes | The function to call when RUN is clicked |
| `description` | `str` | No | Sub-title text on the card |
| `category` | `str` | No | Used to group/filter cards (e.g. `"Acoustics"`) |
| `params` | `list[dict]` | No | Parameter definitions (see below) |

### Parameter Schema

Each entry in `params` is a dict:

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | `str` | Yes | Must match the function's keyword argument name |
| `type` | `str` | Yes | `"float"`, `"int"`, `"str"`, or `"bool"` |
| `default` | any | No | Pre-filled value in the input widget |
| `min` | numeric | No | Minimum value (clamps the spin box) |
| `max` | numeric | No | Maximum value (clamps the spin box) |
| `description` | `str` | No | Tooltip / label text |

---

## Return Value

A calculation function may return **any value**. The MODULE LOADER
pretty-prints:

- `dict` — rendered as a key-value table
- `float` / `int` — shown as a single number
- `str` — shown as plain text
- `list` — rendered as a numbered list

---

## Fallback Introspection

If `SOUL_CALCULATIONS` is **absent**, the loader introspects all top-level
public callables in the module and auto-generates parameter forms from Python
type hints. This mode is lower-fidelity (no descriptions, no min/max) but
requires zero extra code.

```python
# Minimal plugin — no SOUL_CALCULATIONS needed
def attenuation_db(power_w: float, distance_m: float) -> float:
    """Inverse-square SPL loss."""
    import math
    return -20.0 * math.log10(distance_m) if distance_m > 0 else 0.0
```

---

## Optional Metadata Attributes

| Module attribute | Type | Purpose |
|-----------------|------|---------|
| `SOUL_VERSION` | `str` | Displayed in the module info card |
| `SOUL_DESCRIPTION` | `str` | Sub-title on the module info card |
| `SOUL_AUTHOR` | `str` | Attribution line |
| `SOUL_LICENSE` | `str` | License identifier shown in UI |

---

## Lifecycle

1. `plugins/` directory is scanned at GUI startup (300 ms delayed start).
2. Each `.py` file is imported with `importlib.import_module`.
3. Discovered calculations are registered in the global `ModuleRegistry`.
4. Clicking **SCAN plugins/** re-runs discovery — new files are added,
   removed files are unregistered.
5. Clicking **RUN** on a card dispatches the function in a `QThread`
   (`CalcWorker`) so the UI remains responsive during long calculations.

---

## Error Handling

- **Import errors** are caught and displayed as an error card — no crash.
- **Runtime errors** in the function are caught by `CalcWorker` and
  displayed inline; the rest of the UI is unaffected.
- Plugins do **not** have access to the GUI internals; they receive only
  the parameter values from the form.

---

## Example: BPF Range Calculator

```python
# plugins/bpf_calc.py
"""
Blade Pass Frequency range calculator.
Given motor count, blade count, and RPM range, returns the expected BPF band.
"""
SOUL_VERSION     = "1.0"
SOUL_DESCRIPTION = "BPF range estimator for drone platform identification"

def bpf_range(
    motor_count: int,
    blade_count: int,
    rpm_min: float,
    rpm_max: float,
) -> dict:
    """Return the expected BPF band in Hz."""
    rps_min = rpm_min / 60.0
    rps_max = rpm_max / 60.0
    bpf_min = motor_count * blade_count * rps_min
    bpf_max = motor_count * blade_count * rps_max
    return {
        "bpf_min_hz": round(bpf_min, 1),
        "bpf_max_hz": round(bpf_max, 1),
        "band_hz":    round(bpf_max - bpf_min, 1),
    }

SOUL_CALCULATIONS = [
    {
        "name":        "BPF Range",
        "fn":          bpf_range,
        "description": "Blade Pass Frequency band for a given RPM range",
        "category":    "Detection",
        "params": [
            {"name": "motor_count", "type": "int",   "default": 4,      "min": 1, "max": 12},
            {"name": "blade_count", "type": "int",   "default": 3,      "min": 2, "max": 8},
            {"name": "rpm_min",     "type": "float", "default": 3000.0, "min": 100.0, "max": 50000.0},
            {"name": "rpm_max",     "type": "float", "default": 8000.0, "min": 100.0, "max": 50000.0},
        ],
    }
]
```

---

## License Note

All plugins you write and distribute are subject to the same license terms as
SoulMusic itself (see `LICENSE`). Specifically, **Clause D (No Harmful Use)**
applies to all derivative works including plugins. Plugins may not be used
to cause harm to human life under any circumstances.
