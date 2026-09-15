"""Bonus F - Simulated IoT sensor feed (documented as SIMULATED, not real).

Honesty first: no ESP32 is attached in this deployment. This module *simulates*
the exact JSON the firmware would publish, so the API contract is real and the
firmware only has to replace `read()` with an HTTP/MQTT client.

Published firmware contract (what a real node would send)
--------------------------------------------------------
    POST /api/sensors/ingest
    {"device_id": "esp32-field-1", "soil_moisture_pct": 41.2, "temperature_c": 29.4,
     "humidity_pct": 63.0, "soil_ph": 6.6, "battery_pct": 88, "rssi_dbm": -67,
     "ts": "2026-09-11T05:40:00Z"}

Simulation model
----------------
* deterministic per device id + time bucket (`seed`), so tests are reproducible:
  the same timestamp always yields the same reading;
* soil moisture follows a drain/irrigate sawtooth (drains ~1.1 %/h, refilled to
  ~62 % when it crosses 28 %) - which makes the irrigation advice interesting;
* temperature/humidity follow a smooth diurnal sinusoid + small noise;
* battery drains 0.4 %/h and wraps; RSSI jitters around -67 dBm.

`HISTORY_MINUTES` is generated on demand (no background thread, no state that
can leak between requests).
"""
from __future__ import annotations

import hashlib
import math
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .app_phrases import say
from .i18n import normalise

# Deployment epoch anchors the simulated battery drain so the demo node reads a
# realistic, slowly-falling charge instead of an arbitrary value derived from the
# absolute clock. A node lasts ~10 days on one charge at 0.4 %/h.
DEPLOY_EPOCH = 1_787_000_000.0  # 2026-08-17T00:00:00Z (fixed, deterministic)

DEVICES = {
    "esp32-field-1": {"name": "North field node", "crop": "tomato", "area_ha": 1.2},
    "esp32-field-2": {"name": "South field node", "crop": "potato", "area_ha": 0.8},
    "esp32-greenhouse": {"name": "Polyhouse node", "crop": "bell_pepper", "area_ha": 0.3},
}
# device id -> phrase row, so the card's node name follows the language selector
DEVICE_NAME_KEYS = {"esp32-field-1": {"en": "dev_north", "hi": "dev_north", "gu": "dev_north"},
                    "esp32-field-2": {"en": "dev_south", "hi": "dev_south", "gu": "dev_south"}}
DEFAULT_DEVICE = "esp32-field-1"
SAMPLE_INTERVAL_S = 300          # firmware publishes every 5 minutes
DRAIN_PCT_PER_H = 1.1
IRRIGATE_TRIGGER_PCT = 28.0
IRRIGATE_REFILL_PCT = 62.0
BATTERY_DRAIN_PCT_PER_H = 0.4
FIRMWARE = "agrismart-node/1.3.2 (simulated)"


def _rng_for(device_id: str, bucket: int) -> random.Random:
    seed = hashlib.sha256(f"{device_id}|{bucket}".encode()).hexdigest()[:16]
    return random.Random(int(seed, 16))


def read(device_id: str = DEFAULT_DEVICE, at: float | None = None) -> dict[str, Any]:
    """Deterministic simulated reading for `device_id` at epoch `at`."""
    device_id = device_id if device_id in DEVICES else DEFAULT_DEVICE
    at = float(at if at is not None else time.time())
    bucket = int(at // SAMPLE_INTERVAL_S)
    rng = _rng_for(device_id, bucket)

    minute_of_day = (at / 60.0) % 1440
    temp = 27.5 + 6.0 * math.sin((minute_of_day - 360) / 1440 * 2 * math.pi) + rng.uniform(-0.6, 0.6)
    hum = 62.0 - 14.0 * math.sin((minute_of_day - 360) / 1440 * 2 * math.pi) + rng.uniform(-3, 3)

    # sawtooth: hours since an irrigation event
    cycle_h = (IRRIGATE_REFILL_PCT - IRRIGATE_TRIGGER_PCT) / DRAIN_PCT_PER_H  # ~31 h
    hours_in_cycle = (at / 3600.0) % cycle_h
    soil = IRRIGATE_REFILL_PCT - DRAIN_PCT_PER_H * hours_in_cycle + rng.uniform(-1.2, 1.2)
    soil = max(12.0, min(78.0, soil))

    hours_since_deploy = max(0.0, (at - DEPLOY_EPOCH) / 3600.0)
    battery = 100.0 - (BATTERY_DRAIN_PCT_PER_H * hours_since_deploy) % 100.0
    return {
        "device_id": device_id,
        "device_name": DEVICES[device_id]["name"],
        "crop": DEVICES[device_id]["crop"],
        "area_ha": DEVICES[device_id]["area_ha"],
        "soil_moisture_pct": round(soil, 1),
        "temperature_c": round(temp, 1),
        "humidity_pct": round(hum, 1),
        "soil_ph": round(6.4 + rng.uniform(-0.4, 0.4), 2),
        "battery_pct": round(battery, 1),
        "rssi_dbm": int(-67 + rng.uniform(-6, 6)),
        "ts": datetime.fromtimestamp(at, tz=timezone.utc).isoformat(timespec="seconds"),
        "epoch": at,
        "firmware": FIRMWARE,
        "simulated": True,
    }


def latest(device_id: str = DEFAULT_DEVICE, lang: str | None = None) -> dict[str, Any]:
    """Most recent simulated reading + a health line for the UI card."""
    r = read(device_id)
    battery = r["battery_pct"]
    r["status"] = ("healthy" if battery > 40 else "battery-low" if battery > 15 else "charge-now")
    r["status_label"] = say({"healthy": "st_healthy", "battery-low": "st_battery_low",
                             "charge-now": "st_charge_now"}[r["status"]], lang)
    r["needs_irrigation"] = r["soil_moisture_pct"] < IRRIGATE_TRIGGER_PCT
    r["next_sample_in_s"] = int(SAMPLE_INTERVAL_S - (time.time() % SAMPLE_INTERVAL_S))
    r["note"] = say("sim_note", lang)
    key = DEVICE_NAME_KEYS.get(device_id, {}).get(normalise(lang))
    r["device_name"] = say(key, lang) if key else r.get("device_name")
    r["language"] = normalise(lang)
    return r


def history(device_id: str = DEFAULT_DEVICE, samples: int = 24,
            lang: str | None = None) -> dict[str, Any]:
    """Last `samples` readings, oldest first (default 24 x 5 min = 2 h)."""
    samples = max(1, min(int(samples), 288))
    now = time.time()
    rows = [read(device_id, at=now - (samples - 1 - i) * SAMPLE_INTERVAL_S) for i in range(samples)]
    soils = [r["soil_moisture_pct"] for r in rows]
    temps = [r["temperature_c"] for r in rows]
    return {
        "device_id": device_id if device_id in DEVICES else DEFAULT_DEVICE,
        "interval_s": SAMPLE_INTERVAL_S,
        "count": len(rows),
        "simulated": True,
        "samples": rows,
        "summary": {
            "soil_moisture_min": min(soils), "soil_moisture_max": max(soils),
            "soil_moisture_avg": round(sum(soils) / len(soils), 1),
            "temperature_min": min(temps), "temperature_max": max(temps),
            "trend": ("drying" if soils[-1] < soils[0] else
                      "wetting" if soils[-1] > soils[0] else "stable"),
            "trend_label": say("trend_" + ("drying" if soils[-1] < soils[0] else
                                           "wetting" if soils[-1] > soils[0] else "stable"), lang),
        },
        "language": normalise(lang),
    }


def devices() -> list[dict[str, Any]]:
    out = []
    for did, meta in DEVICES.items():
        out.append({"device_id": did, **meta, "simulated": True})
    return out


def ingest(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a real node's payload (firmware contract above) and echo it back."""
    required = ("device_id", "soil_moisture_pct", "temperature_c")
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"missing sensor fields: {', '.join(missing)}")
    soil = float(payload["soil_moisture_pct"])
    if not 0 <= soil <= 100:
        raise ValueError("soil_moisture_pct must be 0-100")
    temp = float(payload["temperature_c"])
    if not -20 <= temp <= 70:
        raise ValueError("temperature_c must be between -20 and 70")
    return {
        "accepted": True,
        "device_id": payload["device_id"],
        "received": {k: payload[k] for k in ("device_id", "soil_moisture_pct", "temperature_c")
                     if k in payload},
        "overrides_simulation": True,
        "echo": {**payload, "server_ts": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "note": "Payload accepted. In this deployment readings remain simulated unless "
                "SENSOR_INGEST_ENABLED is on.",
    }


def expires_at() -> str:
    """When the current simulation bucket rolls over (for cache headers)."""
    nxt = (int(time.time() // SAMPLE_INTERVAL_S) + 1) * SAMPLE_INTERVAL_S
    return datetime.fromtimestamp(nxt, tz=timezone.utc).isoformat(timespec="seconds")


def as_timeseries(device_id: str = DEFAULT_DEVICE, samples: int = 24) -> list[dict[str, Any]]:
    """Chart-ready rows (t, soil, temp, humidity) for the dashboard sparkline."""
    h = history(device_id, samples)
    return [{"t": r["ts"], "soil": r["soil_moisture_pct"], "temp": r["temperature_c"],
             "humidity": r["humidity_pct"]} for r in h["samples"]]


def strip_now() -> list[int]:
    """1-D array of soil moisture - handy for tests and plotting."""
    return [r["soil"] for r in as_timeseries(samples=48)]


def simulated_window(start_iso: str, minutes: int = 60) -> list[dict[str, Any]]:
    """Replay a window from an ISO start time (used by the demo script)."""
    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    t0 = start.timestamp()
    out = []
    for i in range(0, max(1, minutes // 5)):
        out.append(read(at=t0 + i * SAMPLE_INTERVAL_S))
    return out


def _timedelta_hours(h: float) -> timedelta:  # pragma: no cover - small helper
    return timedelta(hours=h)
