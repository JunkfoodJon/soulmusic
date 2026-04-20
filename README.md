# SoulMusic — Open-Source Acoustic Counter-Drone System

> Hostile drones cost $300. So does stopping them — if someone builds it right.

**Live site → [soulmusic.life](https://soulmusic.life/#overview)**

SoulMusic is a passive-acoustic drone detection and alert system you can build from
off-the-shelf consumer hardware for roughly **$300**. It listens for the characteristic
rotor harmonics of small UAVs, pinpoints their direction, and fires configurable alerts —
no RF jamming, no special licences, entirely within US federal law.

## What it does

| Capability | Detail |
|---|---|
| 🎙️ 360° acoustic detection | 4-mic MEMS array + TDOA bearing, ±10° accuracy |
| 🧠 Edge AI classification | MobileNetV2 CNN runs on-device (Raspberry Pi 4) |
| 📡 Real-time alerts | Push notifications, siren/strobe GPIO, webhook |
| 🔓 Fully open source | MIT licence — schematics, dataset, model weights included |

## Quick start

```bash
git clone https://github.com/JunkfoodJon/soulmusic.git
cd soulmusic && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# See index.html #build section or soulmusic.life/#build for full instructions
```

## Budget (~$300)

Raspberry Pi 4 · USB audio interface · 4 × MEMS microphones · weatherproof enclosure ·
optional PoE hat · optional siren/strobe relay. Full bill of materials at
[soulmusic.life/#bom](https://soulmusic.life/#bom).

## Legal

This system is **detection and alerting only**. It does not jam radio frequencies or GPS
signals (federal crimes under 47 U.S.C. § 333 / FAA regulations). See
[soulmusic.life/#legal](https://soulmusic.life/#legal) for a full compliance overview.

## Licence

[MIT](LICENSE) — free for personal and commercial use.
