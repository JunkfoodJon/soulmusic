# SoulMusic — Defensive Acoustic Counter-Planar Research Platform

## Mission
A non-lethal, non-RF-interfering defensive research platform that uses
acoustic resonance to disrupt MEMS inertial measurement units (IMUs) in
hostile drones.  Built on doppel.stream's proven WebRTC stack for
ultra-low-latency operator ↔ planar control.

## Legal Status
- ✅ Research, development, prototyping: **Legal**
- ✅ Acoustic emission (not RF): **No FCC jurisdiction**
- ✅ Sale to law enforcement / military: **Legal**
- ⚠️ Field deployment against hostile drones: **Gray** (18 USC §32 vs self-defense, untested)
- ✅ Patent / publication: **Legal**

---

## Scientific Basis

### Published Research
| Paper | Authors | Year | Key Finding |
|-------|---------|------|-------------|
| *Rocking Drones with Intentional Sound Noise on Gyroscopic Sensors* | Son et al. (KAIST) | 2015 | Ultrasonic frequencies matching MEMS gyro resonance (19–30 kHz) cause false readings → loss of flight stability |
| *WALNUT: Waging Attacks on Long-range Ultrasonic Noise* | Trippel et al. (U. Michigan) | 2017 | Ultrasonic injection attacks on MEMS accelerometers via acoustic resonance |
| *Injected and Delivered: Fabricating Implicit Control over Actuation Systems* | Tu et al. | 2018 | Expanded acoustic injection to broader range of MEMS sensors |

### How It Works
MEMS gyroscopes (e.g. InvenSense MPU-6050/6500/9250, Bosch BMI055/088)
contain vibrating proof masses that detect angular rate.  These masses have
**mechanical resonant frequencies** — typically 20–30 kHz for consumer/hobby
flight controllers.

When an external acoustic source matches this resonant frequency, the proof
mass couples with the sound energy and produces erroneous readings.  The
flight controller's PID loop sees phantom rotation → compensates → induces
real instability → the target cannot maintain stable flight.

### Key Parameters
- **Target frequencies**: 19–30 kHz (varies by specific MEMS chip)
- **Sweep approach**: Chirp across 18–35 kHz to cover unknown sensor models
- **Effective range**: Published research shows effects at 1–5 meters (bench)
  — range extension via phased array beamforming (see below)
- **Power**: Ultrasonic transducer arrays, 100–150 dB SPL at source
- **Beam focusing**: 16×16 phased array (~110mm sq) gives ~7.5° beam, +24 dB
  coherent gain, near-field focusing adds +6 dB at focal point
- **Human safety**: >20 kHz is above human hearing threshold; reasonable
  power levels are safe for bystanders

### Acoustic Beamforming
Omnidirectional emission wastes ~99% of energy in directions that aren't
the target.  At λ≈14mm (25 kHz), a compact phased array with λ/2 element
spacing can form a tight, electronically steered beam.

**Phased Array**: 16×16 grid of piezo transducers, ~110mm square face.
Per-element phase delays create constructive interference in exactly one
direction.  No moving parts — instant re-aim, can track targets faster
than any gimbal.

**Near-field Focusing**: For engagement ranges of 1–5m (within the array's
near-field boundary D²/4λ ≈ 0.22m), spherical wavefront correction
converges energy at a point rather than a line — significant additional
SPL at the target.

**Vortex Beam Mode**: Helical phase pattern creates an acoustic vortex
that carries orbital angular momentum.  The spiral wavefront resists
spreading — tighter beam at longer range.  Like acoustic rifling.

**Receive Beamforming**: Same phase delays applied to a MEMS microphone
array create a directional spatial filter for probe reflection capture.
Rejects noise from all directions except the target.

| Array Config | Elements | Beamwidth | Gain | Physical Size |
|-------------|----------|-----------|------|---------------|
| 8×8 grid | 64 | ~15° | +18 dB | ~55mm sq |
| 16×16 grid | 256 | ~7.5° | +24 dB | ~110mm sq |
| Concentric rings (49) | 49 | ~12° | +17 dB | ~90mm dia |

---

## System Architecture

### Mapping from Doppel.stream
```
Doppel.stream              →  SoulMusic
─────────────                  ─────────
StreamHostDG.py (encoder)  →  planar_host.py (onboard Pi)
viewer.html (browser)      →  operator.py (control station)
relay_registry.py          →  signal_server.py (discovery)
ws_proxy.py                →  (reuse or direct P2P)
Gamepad → data channel     →  Flight commands → data channel
Video ← WebRTC track       →  Camera feed ← WebRTC track
```

### Physical Components
```
┌─────────────────────────────────────────────┐
│  OPERATOR STATION                           │
│  (Laptop / Desktop)                         │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │  Gamepad /   │  │  operator.py         │  │
│  │  RC TX sim   │→ │  - WebRTC client     │  │
│  └─────────────┘  │  - Video feed display │  │
│                    │  - Telemetry HUD      │  │
│                    │  - Acoustic controls  │  │
│                    └──────────┬───────────┘  │
└───────────────────────────────┼──────────────┘
                                │ WebRTC (P2P or TURN relay)
                                │ Video ↑  Commands ↓
┌───────────────────────────────┼──────────────┐
│  PLANAR UNIT (Raspberry Pi 4/5)   │              │
│  ┌────────────────────────────┴────────────┐ │
│  │  planar_host.py                         │ │
│  │  - WebRTC server (aiortc)               │ │
│  │  - Camera → video track                 │ │
│  │  - Telemetry → data channel             │ │
│  │  - Commands → MAVLink serial            │ │
│  │  - Acoustic module control              │ │
│  └─────────┬──────────┬──────────┬─────────┘ │
│            │          │          │            │
│  ┌─────────┴──┐ ┌─────┴────┐ ┌──┴─────────┐ │
│  │ Pi Camera  │ │ UART to  │ │ I²S / PWM  │ │
│  │ Module v3  │ │ FC (APM) │ │ → Amp →    │ │
│  │ 1080p30    │ │ MAVLink  │ │ Ultrasonic │ │
│  │            │ │          │ │ Transducer │ │
│  │            │ │          │ │ Array      │ │
│  └────────────┘ └──────────┘ └────────────┘  │
└──────────────────────────────────────────────┘
```

### Data Channels (WebRTC)
| Channel | Direction | Content |
|---------|-----------|---------|
| `video` | Planar → Operator | Pi Camera H.264 stream |
| `control` | Operator → Planar | JSON: `{throttle, yaw, pitch, roll}` at 50Hz |
| `telemetry` | Planar → Operator | JSON: `{lat, lon, alt, heading, batt, imu, gps_fix}` at 10Hz |
| `acoustic` | Operator → Planar | JSON: `{enabled, freq_start, freq_end, sweep_ms, power}` |
| `detection` | Planar → Operator | JSON: `{targets: [{bearing, distance_est, classification}]}` |

### Passive Doppler Detection

The speed-of-sound bottleneck: at 3m range, the active probe cycle wastes
17.5ms on round-trip sound travel — 90% of each cycle.  At 80 m/s closing
speed, the target traverses a 5m engagement envelope in 62.5ms = only 3
probe cycles.  Not enough to identify + attack.

**Solution**: Listen to the target's own propeller noise.  Every propeller
produces a blade-pass frequency (BPF = RPM × blades / 60) with harmonics.
This signature is audibly unique per platform class.  The Doppler effect
shifts these frequencies when the target is approaching:

```
f_observed = f_true × c / (c − v)
```

At 30 m/s approach speed: ~9% upshift.  At 80 m/s: ~23%.

**What passive Doppler gives us for free:**
1. **Detection at range** — propeller noise travels at the speed of sound
   toward us; we can hear a quad at 50–200m depending on ambient noise
2. **Radial speed** — frequency shift directly maps to approach velocity
3. **Bearing** — beamformed directional listen triangulates source direction
4. **Platform identification** — BPF range + motor count + harmonic pattern
   → match against platform database → known MEMS sensor model
5. **Pre-loaded attack** — MEMS model → resonant frequency → burst params
   are *already armed* on the emitter before the target reaches range
6. **Doppler pre-compensation** — emission frequency is pre-shifted based on
   radial speed so the moving target receives the correct resonant frequency

**Zero-probe fire path**: Passive detect → platform ID → MEMS lookup →
pre-load emitter → Doppler pre-compensate for closing speed → target enters range → operator enables → burst fires
at the exact resonant frequency.  No probe cycle needed.

```
                    Passive Detection Pipeline
                    ─────────────────────────────
  Propeller noise → Mic array → Beamformed capture (50ms)
                                    │
                                    ├─ FFT → Peak extraction → BPF + harmonics
                                    │
                                    ├─ Doppler shift → Radial speed + corrected BPF
                                    │
                                    ├─ Platform DB match → MEMS sensor model
                                    │
                                    └─ MEMS_PROFILES lookup → Pre-armed burst params
                                    │
                                    └─ Doppler pre-compensation → Emission freq adjusted for radial speed
```

### Signaling Flow
1. Planar unit boots → connects to signal server via WebSocket
2. Operator opens control station → fetches planar list from signal server
3. WebRTC offer/answer exchanged through signal server
4. P2P connection established (STUN, TURN fallback)
5. Operator has live video + full flight control + acoustic module control

---

## Hardware BOM (Research Prototype)

| Component | Purpose | Est. Cost |
|-----------|---------|-----------|
| Raspberry Pi 5 (8GB) | Onboard compute | $80 |
| Pi Camera Module v3 | FPV video feed | $25 |
| Pixhawk / APM flight controller | Flight stabilization + MAVLink | $50–150 |
| Planar frame + motors + ESCs + props | Airframe (5" or 7" quad) | $150–300 |
| LiPo battery (4S 1500mAh) | Power | $25 |
| Ultrasonic transducer array (40kHz piezo) | Acoustic emitter (research) | $20–50 |
| Audio amplifier board (Class D, I²S) | Drive transducers | $15 |
| USB LTE modem (or Wi-Fi for short range) | Network uplink for WebRTC | $30 |
| GPS module (u-blox) | Position telemetry | $15 |

**Estimated total**: ~$400–700 for a research prototype

---

## File Structure
```
SoulMusic/
├── ARCHITECTURE.md          ← this file
├── goals.md                 ← project philosophy + vision
├── legality.md              ← legal framework + technical justification
├── HomeworkCores.md         ← physics education (beamforming, MEMS, Doppler, etc.)
├── models.md                ← hardware build catalog (Build 1–4)
├── buildschem.md            ← wiring schematics for builds 2 & 4
├── testsubjects.md          ← drone MEMS gyroscope catalog by tier
├── planar_host.py           ← onboard Pi: WebRTC + MAVLink + acoustic
├── test_harness.py          ← 122 software-only tests (all passing)
├── bench_test.py            ← physical hardware bench test script
├── product.html             ← investor-facing product page
├── acoustic/
│   ├── resonance.py         ← frequency sweep + burst waveform generator + Doppler pre-compensation + MEMS_PROFILES database
│   ├── emitter.py           ← hardware interface (I²S / PWM output) + SubharmonicLadder support
│   ├── beam.py              ← phased array beamforming (steering + focusing + vortex)
│   └── probe.py             ← adaptive shell characterization (probe → analyze → adapt)
├── flight/
│   ├── mavlink_bridge.py    ← MAVLink serial ↔ command translation
│   └── telemetry.py         ← sensor data collection + packaging
├── detection/
│   └── acoustic_detect.py   ← passive Doppler detection + platform ID + pre-loaded attack
└── requirements.txt

### Not Yet Created
├── operator.py              ← (planned) control station: WebRTC client + HUD
├── signal_server.py         ← (planned) discovery + WebRTC signaling relay
└── detection/
    └── visual_tracker.py    ← (planned) OpenCV target detection from camera
```

---

## Development Phases

### Phase 1: Control Platform (reuse doppel.stream WebRTC)
- [x] planar_host.py — aiortc WebRTC host on Pi, camera video track
- [ ] operator.py — connect to planar unit, display video, send gamepad input
- [ ] signal_server.py — minimal signaling relay
- [x] MAVLink bridge — translate gamepad axes to flight commands

### Phase 2: Detection
- [ ] Visual target tracker (OpenCV, YOLO-based)
- [x] Acoustic signature detection (propeller harmonics)
- [x] Target tracking + bearing estimation

### Phase 3: Acoustic Research Module
- [x] Frequency sweep generator (18–35 kHz chirps)
- [x] Transducer driver interface (I²S/PWM)
- [x] MEMS resonant frequency database
- [x] Bench testing rig + measurement scripts

### Phase 4: Integration
- [ ] Operator HUD with detection overlay
- [ ] Acoustic module control from operator station
- [ ] Autonomous tracking mode (keep emitter aimed at target)
