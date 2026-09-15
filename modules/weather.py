"""Bonus C - Weather intelligence + Bonus B - smart irrigation rules.

Published thresholds (single source of truth, imported by the tests)
-------------------------------------------------------------------
RAIN_DELAY_PCT      = 60   rain probability >= 60 %      -> DELAY irrigation
RAIN_MONITOR_PCT    = 40   40 % <= rain < 60 %           -> MONITOR
SOIL_DRY_PCT        = 30   soil moisture < 30 %          -> drier than ideal
SOIL_TARGET_PCT     = 55   optimal band centre for the water sub-score
HEAT_STRESS_C       = 35   Tmax >= 35 C                  -> irrigate early/late
FROST_C             = 4    Tmin <= 4 C                   -> frost advisory
HUMID_DISEASE_PCT   = 80   RH >= 80 %                    -> fungal pressure up

Everything is deterministic and testable: `assess(...)` is a pure function of
the weather dict + soil reading. Network access happens only in `fetch_weather`
(Open-Meteo, free tier, no API key) and degrades to `source="fallback"`.

Actions returned: IRRIGATE_NOW | DELAY | MONITOR | NO_ACTION
"""
from __future__ import annotations

import math
import time
from typing import Any

import requests

from .app_phrases import say, wcode_label
from .i18n import normalise, t

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

RAIN_DELAY_PCT = 60
RAIN_MONITOR_PCT = 40
SOIL_DRY_PCT = 30
SOIL_TARGET_PCT = 55
HEAT_STRESS_C = 35.0
FROST_C = 4.0
HUMID_DISEASE_PCT = 80

IRRIGATE_NOW = "IRRIGATE_NOW"
DELAY = "DELAY"
MONITOR = "MONITOR"
NO_ACTION = "NO_ACTION"

# WMO weather interpretation codes -> (english label, is_rainy, is_severe)
WMO_CODES: dict[int, tuple[str, bool, bool]] = {
    0: ("Clear sky", False, False),
    1: ("Mainly clear", False, False),
    2: ("Partly cloudy", False, False),
    3: ("Overcast", False, False),
    45: ("Fog", False, False),
    48: ("Depositing rime fog", False, False),
    51: ("Light drizzle", True, False),
    53: ("Moderate drizzle", True, False),
    55: ("Dense drizzle", True, False),
    56: ("Light freezing drizzle", True, True),
    57: ("Dense freezing drizzle", True, True),
    61: ("Slight rain", True, False),
    63: ("Moderate rain", True, True),
    65: ("Heavy rain", True, True),
    66: ("Light freezing rain", True, True),
    67: ("Heavy freezing rain", True, True),
    71: ("Slight snowfall", False, True),
    73: ("Moderate snowfall", False, True),
    75: ("Heavy snowfall", False, True),
    77: ("Snow grains", False, True),
    80: ("Slight rain showers", True, False),
    81: ("Moderate rain showers", True, True),
    82: ("Violent rain showers", True, True),
    85: ("Slight snow showers", False, True),
    86: ("Heavy snow showers", False, True),
    95: ("Thunderstorm", True, True),
    96: ("Thunderstorm with slight hail", True, True),
    99: ("Thunderstorm with heavy hail", True, True),
}

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL_S = 600


def describe_code(code: int | None) -> tuple[str, bool, bool]:
    if code is None:
        return ("Unknown", False, False)
    return WMO_CODES.get(int(code), ("Unknown", False, False))


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


# --------------------------------------------------------------------------- #
# fetching (network)                                                          #
# --------------------------------------------------------------------------- #
def geocode(city: str, timeout: float = 6.0) -> dict[str, Any] | None:
    """City name -> {name, country, latitude, longitude}. None when not found."""
    if not city or not str(city).strip():
        return None
    try:
        r = requests.get(
            GEOCODE_URL,
            params={"name": str(city).strip(), "count": 1, "language": "en", "format": "json"},
            timeout=timeout,
        )
        r.raise_for_status()
        results = (r.json() or {}).get("results") or []
    except Exception:
        return None
    if not results:
        return None
    top = results[0]
    return {
        "name": top.get("name") or city,
        "country": top.get("country"),
        "admin1": top.get("admin1"),
        "latitude": top.get("latitude"),
        "longitude": top.get("longitude"),
    }


def fetch_weather(
    city: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    timeout: float = 8.0,
    use_cache: bool = True,
    lang: str | None = None,
) -> dict[str, Any]:
    """Live weather for a city or explicit coordinates.

    Always returns a dict. On any failure it returns
    ``{"ok": False, "source": "fallback", "error": <reason>, ...}`` so callers can
    fall back to manually supplied values (FR-10: never a stack trace).
    """
    place: dict[str, Any] = {}
    if latitude is None or longitude is None:
        place = geocode(city or "", timeout=timeout) or {}
        latitude = place.get("latitude")
        longitude = place.get("longitude")
    if latitude is None or longitude is None:
        return {
            "ok": False, "source": "fallback", "city": city,
            "error": f"could not resolve location '{city}'" if city else "no location given",
            "note": t("weather_offline"),
        }

    key = f"{round(float(latitude), 3)},{round(float(longitude), 3)}"
    now = time.time()
    if use_cache and key in _CACHE and now - _CACHE[key][0] < CACHE_TTL_S:
        cached = dict(_CACHE[key][1])
        cached["cached"] = True
        return localize_weather(cached, lang)      # cache holds English only

    params = {
        "latitude": latitude, "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weather_code",
        "hourly": "precipitation_probability", "forecast_days": 7, "timezone": "auto",
    }
    try:
        r = requests.get(FORECAST_URL, params=params, timeout=timeout)
        r.raise_for_status()
        raw = r.json()
    except Exception as exc:  # network down, rate-limited, malformed ...
        return {
            "ok": False, "source": "fallback", "city": city,
            "latitude": latitude, "longitude": longitude,
            "error": f"{type(exc).__name__}: {exc}", "note": t("weather_offline"),
        }

    cur = raw.get("current") or {}
    daily = raw.get("daily") or {}
    hourly = raw.get("hourly") or {}
    code = cur.get("weather_code")
    label, rainy, severe = describe_code(code)
    days: list[dict[str, Any]] = []
    for i, date in enumerate(daily.get("time", []) or []):
        def _at(seq, idx=i):
            seq = seq or []
            return seq[idx] if idx < len(seq) else None
        c = _at(daily.get("weather_code"))
        dlabel, _, _ = describe_code(c)
        days.append({
            "date": date,
            "t_max": _at(daily.get("temperature_2m_max")),
            "t_min": _at(daily.get("temperature_2m_min")),
            "rain_mm": _at(daily.get("precipitation_sum")),
            "rain_probability": _at(daily.get("precipitation_probability_max")),
            "code": c, "condition": dlabel,
        })
    next12 = [p for p in (hourly.get("precipitation_probability") or [])[:12] if p is not None]

    out: dict[str, Any] = {
        "ok": True, "source": "open-meteo",
        "city": place.get("name") or city, "country": place.get("country"),
        "admin1": place.get("admin1"),
        "latitude": latitude, "longitude": longitude, "timezone": raw.get("timezone"),
        "temperature_c": cur.get("temperature_2m"),
        "humidity_pct": cur.get("relative_humidity_2m"),
        "precipitation_mm": cur.get("precipitation"),
        "wind_kph": cur.get("wind_speed_10m"),
        "code": code, "condition": label,   # localize_weather() adds condition_en + language
        "is_rainy_now": rainy, "is_severe": severe,
        "rain_next_12h_pct": max(next12) if next12 else None,
        "daily": days,
        "cached": False,
        "fetched_at": now,
    }
    d0 = days[0] if days else {}
    out["t_max_c"] = d0.get("t_max")
    out["t_min_c"] = d0.get("t_min")
    out["rain_today_mm"] = d0.get("rain_mm")
    out["rain_probability_pct"] = d0.get("rain_probability")
    out["weekly_rain_mm"] = round(sum(d["rain_mm"] or 0 for d in days), 2)
    if use_cache:
        _CACHE[key] = (now, dict(out))             # English; localised per request
    return localize_weather(out, lang)


# --------------------------------------------------------------------------- #
# rules (pure)                                                                #
# --------------------------------------------------------------------------- #
def localize_weather(w: dict[str, Any], lang: str | None = None) -> dict[str, Any]:
    """Return a copy with the WMO condition words in `lang`.

    The cache stores English only (see fetch_weather): one Gujarati request must not
    leave an English caller reading Gujarati, or vice versa. `condition_en` always
    keeps the original for logs and tests.
    """
    out = dict(w)
    tag = normalise(lang)
    out["language"] = tag
    english = w.get("condition")
    out["condition_en"] = english
    out["condition"] = wcode_label(w.get("code"), tag, english)
    if isinstance(w.get("daily"), list):
        out["daily"] = [
            {**d, "condition_en": d.get("condition"),
             "condition": wcode_label(d.get("code"), tag, d.get("condition"))}
            for d in w["daily"]
        ]
    return out


def rain_probability(weather: dict[str, Any]) -> float | None:
    """Best available rain-probability signal, in percent (max of daily/12h)."""
    vals = [weather.get("rain_probability_pct"), weather.get("rain_next_12h_pct")]
    vals = [float(v) for v in vals if isinstance(v, (int, float))]
    return max(vals) if vals else None


def assess(
    weather: dict[str, Any] | None = None,
    soil_moisture_pct: float | None = None,
    lang: str | None = None,
) -> dict[str, Any]:
    """Deterministic irrigation decision + human-readable reasons.

    Returns keys: action, action_label, reasons[], alerts[], rain_probability_pct,
    soil_moisture_pct, water_stress, data_completeness, thresholds{}.
    """
    weather = weather or {}
    lang = normalise(lang)
    reasons: list[str] = []
    alerts: list[str] = []
    rain_p = rain_probability(weather)
    rain_mm = weather.get("rain_today_mm")
    tmax = weather.get("t_max_c")
    tmin = weather.get("t_min_c")
    rh = weather.get("humidity_pct")
    if soil_moisture_pct is not None:
        try:
            soil_moisture_pct = float(soil_moisture_pct)
        except (TypeError, ValueError):
            soil_moisture_pct = None

    # ---- advisories independent of the irrigation decision ---------------- #
    if isinstance(tmax, (int, float)) and tmax >= HEAT_STRESS_C:
        alerts.append(say("w_alert_heat", lang, t=f"{tmax:.0f}"))
    if isinstance(tmin, (int, float)) and tmin <= FROST_C:
        alerts.append(say("w_alert_frost", lang, t=f"{tmin:.0f}"))
    if isinstance(rh, (int, float)) and rh >= HUMID_DISEASE_PCT:
        alerts.append(say("w_alert_humid", lang, rh=f"{rh:.0f}"))
    if weather.get("is_severe"):
        alerts.append(say("w_alert_severe", lang, cond=weather.get("condition", "n/a")))

    # ---- decision --------------------------------------------------------- #
    if soil_moisture_pct is None and rain_p is None:
        action = MONITOR
        reasons.append(say("w_no_data", lang))
    elif rain_p is not None and rain_p >= RAIN_DELAY_PCT:
        action = DELAY
        reasons.append(say("w_rain_delay", lang, rain=f"{rain_p:.0f}", thr=RAIN_DELAY_PCT))
    elif soil_moisture_pct is not None and soil_moisture_pct < SOIL_DRY_PCT \
            and (rain_p is None or rain_p < RAIN_MONITOR_PCT):
        action = IRRIGATE_NOW
        reasons.append(say("w_soil_dry", lang, soil=f"{soil_moisture_pct:.0f}",
                           thr=SOIL_DRY_PCT, rain=f"{(rain_p or 0):.0f}"))
    elif rain_p is not None and RAIN_MONITOR_PCT <= rain_p < RAIN_DELAY_PCT:
        action = MONITOR
        reasons.append(say("w_watch_band", lang, rain=f"{rain_p:.0f}",
                           lo=RAIN_MONITOR_PCT, hi=RAIN_DELAY_PCT))
    elif soil_moisture_pct is not None and soil_moisture_pct < SOIL_DRY_PCT:
        action = MONITOR
        reasons.append(say("w_low_rain", lang, soil=f"{soil_moisture_pct:.0f}"))
    elif soil_moisture_pct is not None:
        action = NO_ACTION
        reasons.append(say("w_adequate", lang, soil=f"{soil_moisture_pct:.0f}"))
    else:
        action = MONITOR
        reasons.append(say("w_partial", lang))

    if isinstance(tmax, (int, float)) and tmax >= HEAT_STRESS_C and action == IRRIGATE_NOW:
        reasons.append(say("w_split", lang))
    if isinstance(rain_mm, (int, float)) and rain_mm >= 10:
        reasons.append(say("w_rain_refill", lang, mm=f"{rain_mm:.1f}"))

    provided = [v for v in (soil_moisture_pct, rain_p, tmax, rh) if isinstance(v, (int, float))]
    completeness = round(100 * len(provided) / 4)
    label_map = {IRRIGATE_NOW: "irrigate_now", DELAY: "delay_irrigation",
                 MONITOR: "monitor", NO_ACTION: "no_action"}
    water_stress = "unknown"
    if soil_moisture_pct is not None:
        water_stress = "dry" if soil_moisture_pct < SOIL_DRY_PCT else (
            "optimal" if soil_moisture_pct <= 75 else "waterlogged")

    return {
        "action": action,
        "action_label": t(label_map[action], lang),
        "reasons": reasons,
        "alerts": alerts,
        "rain_probability_pct": rain_p,
        "soil_moisture_pct": soil_moisture_pct,
        "water_stress": water_stress,
        "water_stress_label": say({"dry": "stress_dry", "wet": "stress_wet",
                                  "unknown": "stress_ok"}.get(water_stress, "stress_ok"), lang),
        "data_completeness_pct": completeness,
        "weather_source": weather.get("source", "manual"),
        "is_live": bool(weather.get("ok")),
        "thresholds": {
            "rain_delay_pct": RAIN_DELAY_PCT, "rain_monitor_pct": RAIN_MONITOR_PCT,
            "soil_dry_pct": SOIL_DRY_PCT, "heat_stress_c": HEAT_STRESS_C,
            "frost_c": FROST_C, "humid_disease_pct": HUMID_DISEASE_PCT,
        },
        "disclaimer": t("disclaimer", lang),
    }


def evapotranspiration_proxy(weather: dict[str, Any]) -> float:
    """Very small Hargreaves-style ET0 proxy (mm/day), used only for reporting.

    ET0 ~ 0.0023 * Ra * (Tmean + 17.8) * sqrt(Tmax - Tmin); Ra is approximated by
    a latitude/season-aware daily extra-terrestrial radiation estimate simplified
    to 15 (MJ m^-2 d^-1) as a mid-latitude mean, because the app only needs a
    relative "how thirsty is today" number, clearly labelled as a proxy.
    """
    tmax, tmin = weather.get("t_max_c"), weather.get("t_min_c")
    if not isinstance(tmax, (int, float)) or not isinstance(tmin, (int, float)):
        return 0.0
    tmean = (tmax + tmin) / 2
    ra = 15.0
    return round(0.0023 * ra * (tmean + 17.8) * math.sqrt(max(0.0, tmax - tmin)), 2)
