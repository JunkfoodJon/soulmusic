# SoulMusic — Hardware Bill of Materials

> Verified component list for a complete SoulMusic acoustic counter-UAS build.
> All prices approximate as of Q1 2026. Tested configurations marked ✓.

---

## Required Components

| # | Component | Purpose | Spec | Example Part | Approx. Cost |
|---|-----------|---------|------|-------------|-------------|
| 1 | **MEMS Gyroscope Breakout** | Resonance target sensor (test subject) | MPU-6050 / BMI270 / ICM-42688-P | SparkFun MPU-6050 6DOF IMU, Adafruit BMI270 | $4–$12 |
| 2 | **Ultrasonic Transducer** | Acoustic emission source | 25 kHz–40 kHz piezo, ≥ 113 dB SPL at 30 cm | Murata MA40S4S (40 kHz), PUI Audio UT-1240K (25 kHz) | $3–$8 |
| 3 | **Class-D Amplifier Board** | Drive the transducer | ≥ 10W continuous, I²S or analog input | PAM8610 dual 15W board, MAX98357A I²S | $3–$10 |
| 4 | **USB Audio Interface** | High-sample-rate output + optionally capture | ≥ 96 kHz output, 24-bit | Behringer UMC22, Focusrite Scarlett Solo | $30–$60 |
| 5 | **Microcontroller** | Read MEMS gyro over I²C → serial to PC | Any Arduino-compatible | Arduino Nano (ATmega328P), Arduino Uno | $5–$20 |
| 6 | **Host Computer** | Run `soul_gui.py` / SoulMusic EXE | Python 3.10+, USB 2.0 | Windows 10/11 PC, Raspberry Pi 4/5 | existing |

**Total BOM cost (excluding host computer): ~$45–$110**

---

## Optional Components

| Component | Purpose | Notes |
|-----------|---------|-------|
| MEMS breakout — ICM-42688-P | High-accuracy gyro target for precision calibration | SparkFun Qwiic, ~$15 |
| MEMS breakout — BMI088 | DJI-class gyro (Mavic 3 / Mini 4 primary sensor) | Bosch eval board, ~$20 |
| Signal generator / function gen | Independent frequency verification | Oscilloscope optional backup |
| Digital oscilloscope | Verify transducer output waveform, confirm amplitude | Rigol DS1054Z or OWON equivalent |
| Directional horn attachment | Increase acoustic intensity at range | 3D print from community files |
| Raspberry Pi 4 / 5 | Portable headless deployment on Linux | Works with `install_linux.sh` |

---

## Wiring Overview

See [wiring-diagram.md](wiring-diagram.md) for the full ASCII schematic.

```
Host PC (USB) ──→ USB Audio Interface ──→ Amplifier ──→ Transducer
                                                            ↕ (sound waves)
                                                        MEMS Sensor on target drone
Host PC (USB) ←── Arduino (serial) ←── I²C ←── MEMS Breakout (test bench only)
```

---

## Verified MEMS Sensor Resonance Frequencies

Frequencies from published research and empirical testing. Used by
`acoustic/resonance.py` → `MEMS_PROFILES`.

| Sensor | Resonant Freq | Source |
|--------|--------------|--------|
| InvenSense MPU-6050 | ~27 kHz | Trippel et al. (2017) |
| InvenSense MPU-6500 | ~26 kHz | Trippel et al. (2017) |
| InvenSense MPU-9250 | ~27 kHz | Trippel et al. (2017) |
| InvenSense ICM-20689 | ~24 kHz | Estimated from datasheet |
| InvenSense ICM-42688-P | ~25 kHz | Estimated from datasheet |
| Bosch BMI055 | ~22 kHz | Estimated from datasheet |
| Bosch BMI088 | ~23 kHz | Estimated from datasheet |
| STMicro LSM6DS3 | ~20 kHz | Community bench data |
| TDK IIM-42652 | ~25 kHz | Estimated from datasheet |
| TDK ICM-42670-P | ~24 kHz | Estimated from datasheet |
| Analog Devices ADXL355 | ~28 kHz | Datasheet published resonance |

> ⚠️ **All frequencies above are research estimates.** Actual resonant
> frequencies vary ±2–4 kHz depending on PCB mounting, temperature,
> and manufacturing tolerances. Always perform a calibration sweep with
> `bench_test.py --sweep` before targeting a specific sensor.

---

## Sourcing Notes

- **Transducer**: The Murata MA40S4S is the community-standard part. It is
  40 kHz centre frequency. For sensors resonant below 30 kHz, the PUI
  UT-1240K (25 kHz) produces higher SPL at the target frequency.
- **Amplifier**: The PAM8610 board is sufficient for bench work. For field
  use at range (> 25 m), a higher-power Class-D stage (≥ 50W) with a
  larger driver transducer is required.
- **Audio Interface**: Any interface that supports 96 kHz output in ASIO
  or WASAPI exclusive mode works. The Behringer UMC22 is the lowest-cost
  verified unit.
- **Arduino**: Any ATmega328P or ARM Cortex-M board works. The sketch
  (`tools/gyro_reader.ino`, not yet published) reads gyro data over I²C
  and streams it as CSV at 115200 baud.

---

## Known Hardware Issues

| ID | Issue | Workaround |
|----|-------|-----------|
| BUG-01 | PLATFORM_DB maps DJI Mavic 3 / Mini 4 / Matrice 30 to ICM-42688-P. Teardown data suggests BMI088 primary / ICM-20689 secondary. | Use `bench_test.py --sweep` on a physical unit to verify; report results to maintainers. |
| — | Piezo transducers are highly directional above 30 kHz. Off-axis SPL drops ≥ 6 dB at 15° from the beam centre. | Aim directly at the target sensor location (typically under the top shell, near centre of mass). |

---

*For setup and wiring details, see [wiring-diagram.md](wiring-diagram.md).*
*For legal and ethical use constraints, see [../../LICENSE](../../LICENSE).*
