"""
SoulMusic — flight/telemetry.py
Collects sensor data from the flight controller and packages it
for transmission to the operator via WebRTC data channel.
"""

import logging
import time

LOG = logging.getLogger("flight.telemetry")

_mavlink_conn = None


def init_telemetry(mavlink_conn):
    """Set the MAVLink connection for telemetry reads."""
    global _mavlink_conn
    _mavlink_conn = mavlink_conn


def get_telemetry() -> dict:
    """Read current telemetry from flight controller.

    Returns a JSON-serializable dict with all available sensor data.
    If MAVLink is not connected, returns simulated/empty data.
    """
    telem = {
        "ts": time.time(),
        "lat": 0.0,
        "lon": 0.0,
        "alt": 0.0,         # meters above sea level
        "alt_rel": 0.0,     # meters above home
        "heading": 0.0,     # degrees 0–360
        "speed": 0.0,       # m/s ground speed
        "vspeed": 0.0,      # m/s vertical speed
        "batt_v": 0.0,      # battery voltage
        "batt_pct": 0,      # battery percentage
        "gps_fix": 0,       # 0=no fix, 2=2D, 3=3D
        "gps_sats": 0,      # satellite count
        "armed": False,
        "mode": "UNKNOWN",
        "imu": {
            "roll": 0.0,    # degrees
            "pitch": 0.0,
            "yaw": 0.0,
        },
    }

    if not _mavlink_conn:
        return telem

    try:
        # Read attitude
        att = _mavlink_conn.recv_match(type="ATTITUDE", blocking=False)
        if att:
            import math
            telem["imu"]["roll"] = math.degrees(att.roll)
            telem["imu"]["pitch"] = math.degrees(att.pitch)
            telem["imu"]["yaw"] = math.degrees(att.yaw)
            telem["heading"] = math.degrees(att.yaw) % 360

        # Read GPS
        gps = _mavlink_conn.recv_match(type="GPS_RAW_INT", blocking=False)
        if gps:
            telem["lat"] = gps.lat / 1e7
            telem["lon"] = gps.lon / 1e7
            telem["alt"] = gps.alt / 1000.0
            telem["gps_fix"] = gps.fix_type
            telem["gps_sats"] = gps.satellites_visible

        # Read battery
        batt = _mavlink_conn.recv_match(type="SYS_STATUS", blocking=False)
        if batt:
            telem["batt_v"] = batt.voltage_battery / 1000.0
            telem["batt_pct"] = batt.battery_remaining

        # Read speed
        vfr = _mavlink_conn.recv_match(type="VFR_HUD", blocking=False)
        if vfr:
            telem["speed"] = vfr.groundspeed
            telem["vspeed"] = vfr.climb
            telem["alt_rel"] = vfr.alt

        # Read heartbeat for mode + armed
        hb = _mavlink_conn.recv_match(type="HEARTBEAT", blocking=False)
        if hb:
            from pymavlink import mavutil
            telem["armed"] = bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            mode_map = _mavlink_conn.mode_mapping()
            if mode_map:
                for name, num in mode_map.items():
                    if num == hb.custom_mode:
                        telem["mode"] = name
                        break

    except Exception as e:
        LOG.error(f"Telemetry read error: {e}")

    return telem
