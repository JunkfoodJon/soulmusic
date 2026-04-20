# SoulMusic — Wiring Diagram Reference

> ASCII schematic for the standard SoulMusic bench test and field deployment
> configurations. All connections assume USB host computer unless noted.

---

## Configuration A — Bench Test (Full Pipeline)

Used with `bench_test.py` for hardware validation.

```
┌─────────────────────────────────────────────────────────────────────┐
│  HOST COMPUTER  (Windows 10/11 or Linux PC / Raspberry Pi 4/5)      │
│                                                                       │
│  • soul_gui.py  /  bench_test.py  /  SoulMusic.exe                  │
└───────────┬──────────────────────────┬──────────────────────────────┘
            │ USB (audio out ≥96kHz)    │ USB (serial 115200 baud)
            ▼                           ▼
┌──────────────────┐         ┌──────────────────────┐
│  USB Audio       │         │  Arduino Nano /       │
│  Interface       │         │  Arduino Uno          │
│  (≥96kHz 24-bit) │         │  (ATmega328P)         │
│                  │         │                       │
│  Out L/R ────────┼──────── │  I²C SDA ─────────── │ ─→ MEMS breakout SDA
│  (TRS / RCA)     │         │  I²C SCL ─────────── │ ─→ MEMS breakout SCL
└──────────────────┘         │  3.3V ─────────────── │ ─→ MEMS breakout VCC
            │                │  GND ──────────────── │ ─→ MEMS breakout GND
            ▼                └──────────────────────┘
┌──────────────────┐
│  Class-D Amp     │
│  (PAM8610 or     │
│   equivalent)    │
│                  │
│  + out ──────────┼──────────────────── +  ┐
│  - out ──────────┼──────────────────── -  │ Ultrasonic Transducer
└──────────────────┘                        │ (Murata MA40S4S 40kHz
                                            │  or PUI UT-1240K 25kHz)
                                         ───┘
                                       ↕↕↕ (ultrasonic sound waves)
                              ┌─────────────────────┐
                              │  MEMS Gyroscope      │
                              │  Breakout Board      │
                              │  (MPU-6050, BMI088,  │
                              │   ICM-42688-P, etc.) │
                              └─────────────────────┘
```

### Arduino I²C Wiring Detail

| Arduino Pin | MEMS Breakout Pin | Notes |
|-------------|------------------|-------|
| A4 (SDA) | SDA | 4.7kΩ pull-up to 3.3V recommended |
| A5 (SCL) | SCL | 4.7kΩ pull-up to 3.3V recommended |
| 3.3V | VCC | Most MEMS boards: 3.3V logic |
| GND | GND | Common ground with host is NOT required |

> ⚠️ Some MEMS breakouts accept 5V VCC and have built-in level shifters.
> Check the datasheet for your specific board before wiring.

---

## Configuration B — Field Deployment (Emitter Only)

Used for active deployment. No gyro feedback loop — purely emitter-driven.

```
┌──────────────────────────────┐
│  HOST COMPUTER               │
│  (Laptop / Raspberry Pi)     │
│                              │
│  soul_gui.py  EMITTER tab    │
└──────────┬───────────────────┘
           │ USB (audio out ≥96kHz)
           ▼
┌──────────────────┐
│  USB Audio       │
│  Interface       │
│  (e.g. Focusrite │
│   Scarlett Solo) │
│  Out L ──────────┼──────────────────────────── Signal In
└──────────────────┘              │
                      ┌───────────┴────────┐
                      │  Class-D Amplifier  │
                      │  (PAM8610 ≥10W, or  │
                      │   custom ≥50W rig)  │
                      │  + ─────────────────┼─→  +  ┐
                      │  - ─────────────────┼─→  -  │ Transducer array
                      └─────────────────────┘       │ (one or more)
                                                  ───┘
```

---

## Configuration C — Raspberry Pi Headless (GPIO I²S)

For embedded deployment without a USB audio interface.

```
┌──────────────────────────────────────────────────┐
│  Raspberry Pi 4 / 5                               │
│  GPIO header                                      │
│                                                   │
│  Pin 12  (GPIO18 / PCM_CLK) ───── BCLK ───→ MAX98357A
│  Pin 35  (GPIO19 / PCM_FS)  ───── LRCLK ──→ MAX98357A
│  Pin 40  (GPIO21 / PCM_DOUT)───── DIN ────→ MAX98357A
│  Pin 1   (3.3V)             ───── VIN ────→ MAX98357A
│  Pin 6   (GND)              ───── GND ────→ MAX98357A
│                                                   │
│  (I²C for MEMS sensor)                            │
│  Pin 3   (GPIO2 / SDA1)  ─── SDA → MEMS board    │
│  Pin 5   (GPIO3 / SCL1)  ─── SCL → MEMS board    │
└──────────────────────────────────────────────────┘

MAX98357A Out+ ────→ Transducer +
MAX98357A Out- ────→ Transducer -
```

Enable I²S in `/boot/config.txt`:
```
dtparam=i2s=on
dtoverlay=hifiberry-dac
```

---

## Power Notes

| Component | Current Draw | Supply |
|-----------|-------------|--------|
| MEMS breakout | 3–10 mA | 3.3V from Arduino / Pi 3.3V rail |
| Arduino Nano | 20–40 mA | USB 5V |
| PAM8610 (idle) | ~50 mA | 5–12V DC (9V recommended) |
| PAM8610 (full load 2×15W) | ~4A at 9V | Dedicated PSU required |
| Murata MA40S4S | passive | driven by amp |

> For field use, a 3S LiPo (11.1V, ≥2000mAh) powers the amp and a
> USB power bank runs the Pi or laptop.

---

## Cable Notes

- **Audio line**: use shielded TS/TRS cable from interface to amp input.
  Unshielded cable near the transducer output will pick up RF interference.
- **Transducer wire**: twisted pair, as short as possible (< 30 cm) between
  amp output and transducer terminals. Long runs cause impedance mismatch
  at 25–40 kHz.
- **I²C**: keep total bus length under 30 cm. Add 4.7kΩ pull-ups if lines
  are longer or if using multiple devices on the same bus.

---

*For component sourcing, see [hardware-bom.md](hardware-bom.md).*
*For legal and ethical use constraints, see [../../LICENSE](../../LICENSE).*
