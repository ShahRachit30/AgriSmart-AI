"""Bonus D - AgriSmart Sustainability Index (ASI), a fully published formula.

    ASI = 0.30*water + 0.25*weather + 0.25*disease + 0.20*resource      (0-100)

Each sub-score is 0-100 and built from additive, documented rules so a judge can
recompute any number by hand. Every sub-score returns its own `reasons`, and the
final object lists `contributions` (weight x sub-score) so the total is auditable.

Sub-score rules
---------------
WATER (0.30)  - starts at 100
    soil moisture in [30, 75] %        -> no penalty (ideal band)
    soil < 30 % (dry)                  -> -10 - (30 - m)*0.8
    soil > 75 % (waterlogged)          -> -10 - (m - 75)*0.6
    irrigation action DELAY (rain coming)          -> +5 (kept capped at 100)
    irrigation action IRRIGATE_NOW while raining   -> -8 (wasteful)
    missing soil reading                           -> -15 and flagged "unknown"

WEATHER (0.25) - starts at 100
    rain probability >= 60 %      -> -8   (disease-favourable)
    40-60 %                       -> -4
    RH >= 80 %                    -> -8 ; RH 70-80 % -> -4
    Tmax >= 35 C heat stress      -> -10 ; Tmin <= 4 C frost -> -6
    severe weather now            -> -12
    live (Open-Meteo) data used   -> +6 (better decisions beat guesses)

DISEASE (0.25) - starts at 100
    healthy leaf                  -> no penalty
    low risk                      -> -15 ; moderate -> -35 ; high -> -60 ; critical -> -85
    (a detected disease is a *management* signal, not a verdict on the farmer)

RESOURCE (0.20) - starts at 100
    organic actions listed but no chemical used yet            -> +4
    chemical escalation recommended (high/critical risk)       -> -18
    crop-recommendation agreement with the planted crop        -> +5 ; mismatch -> -5
    IoT/soil sensors connected (simulated feed accepted)       -> +3
    > 5 hectares (harder to scout precisely)                   -> -3

Grades: A >= 80, B >= 65, C >= 50, D >= 35, E < 35.
Band labels: A "excellent", B "good", C "fair", D "poor", E "critical".
"""
from __future__ import annotations

from typing import Any

from .app_phrases import say
from .i18n import normalise

WEIGHTS = {"water": 0.30, "weather": 0.25, "disease": 0.25, "resource": 0.20}
GRADES = ((80, "A"), (65, "B"), (50, "C"), (35, "D"), (0, "E"))
BAND_LABEL = {"A": "excellent", "B": "good", "C": "fair", "D": "poor", "E": "critical"}
RISK_PENALTY = {"low": 15, "moderate": 35, "high": 60, "critical": 85}


def _clip(x: float) -> float:
    return max(0.0, min(100.0, x))


def water_subscore(soil_moisture_pct: float | None, irrigation_action: str | None,
                   raining: bool = False, lang: str | None = None) -> tuple[float, list[str]]:
    score, why = 100.0, []
    if soil_moisture_pct is None:
        score -= 15
        why.append(say("s_moisture_unknown", lang))
    else:
        m = float(soil_moisture_pct)
        if m < 30:
            pen = 10 + (30 - m) * 0.8
            score -= pen
            why.append(say("s_soil_dry", lang, m=f"{m:.0f}", pen=pen))
        elif m > 75:
            pen = 10 + (m - 75) * 0.6
            score -= pen
            why.append(say("s_soil_wet", lang, m=f"{m:.0f}", pen=pen))
        else:
            why.append(say("s_soil_ideal", lang, m=f"{m:.0f}"))
    if irrigation_action == "DELAY":
        score += 5
        why.append(say("s_delayed_ok", lang))
    if irrigation_action == "IRRIGATE_NOW" and raining:
        score -= 8
        why.append(say("s_irrigating_in_rain", lang))
    return _clip(score), why


def weather_subscore(weather: dict[str, Any], lang: str | None = None) -> tuple[float, list[str]]:
    score, why = 100.0, []
    rain_p = weather.get("rain_probability_pct") or weather.get("rain_next_12h_pct")
    rh = weather.get("humidity_pct")
    tmax, tmin = weather.get("t_max_c"), weather.get("t_min_c")
    if isinstance(rain_p, (int, float)):
        if rain_p >= 60:
            score -= 8
            why.append(say("s_rain_fungal", lang, rain=f"{rain_p:.0f}"))
        elif rain_p >= 40:
            score -= 4
            why.append(say("s_rain_watch", lang, rain=f"{rain_p:.0f}"))
    if isinstance(rh, (int, float)):
        if rh >= 80:
            score -= 8
            why.append(say("s_humid_high", lang, rh=f"{rh:.0f}"))
        elif rh >= 70:
            score -= 4
            why.append(say("s_humid_mid", lang, rh=f"{rh:.0f}"))
    if isinstance(tmax, (int, float)) and tmax >= 35:
        score -= 10
        why.append(say("s_heat", lang, t=f"{tmax:.0f}"))
    if isinstance(tmin, (int, float)) and tmin <= 4:
        score -= 6
        why.append(say("s_frost", lang, t=f"{tmin:.0f}"))
    if weather.get("is_severe"):
        score -= 12
        why.append(say("s_severe", lang))
    if weather.get("ok"):
        score += 6
        why.append(say("s_live_weather", lang))
    return _clip(score), why


def disease_subscore(risk: str, is_healthy: bool, lang: str | None = None) -> tuple[float, list[str]]:
    if is_healthy:
        return 100.0, [say("s_healthy_leaf", lang)]
    pen = RISK_PENALTY.get(risk, 35)
    return _clip(100 - pen), [say("s_disease", lang, risk=risk, pen=pen)]


def resource_subscore(risk: str, recommended_crop: str | None, planted_crop: str | None,
                      sensor_connected: bool, area_ha: float | None,
                      lang: str | None = None) -> tuple[float, list[str]]:
    score, why = 100.0, []
    if risk in ("high", "critical"):
        score -= 18
        why.append(say("s_chemical_on_table", lang))
    else:
        score += 4
        why.append(say("s_organic_ok", lang))
    if recommended_crop and planted_crop:
        if recommended_crop.lower() == planted_crop.lower():
            score += 5
            why.append(say("s_crop_match", lang))
        else:
            score -= 5
            why.append(say("s_crop_mismatch", lang, rec=recommended_crop, planted=planted_crop))
    if sensor_connected:
        score += 3
        why.append(say("s_sensor_ok", lang))
    if isinstance(area_ha, (int, float)) and area_ha > 5:
        score -= 3
        why.append(say("s_area_large", lang, area=f"{area_ha:.1f}"))
    return _clip(score), why


def band_label(letter: str, lang: str | None = None) -> str:
    """Grade letter -> localized word ('B' -> 'good' / 'अच्छा' / 'સારું').

    English keeps the original lower-case band word so existing responses and the
    report stay byte-identical; the other languages come from the shared vocabulary.
    """
    word = BAND_LABEL.get(letter, "")
    if not word or normalise(lang) == "en":
        return word
    from .assistant_i18n import localize_band
    return localize_band(word, lang)


def grade_for(total: float) -> str:
    for threshold, letter in GRADES:
        if total >= threshold:
            return letter
    return "E"


def index(
    soil_moisture_pct: float | None = None,
    irrigation_action: str | None = None,
    weather: dict[str, Any] | None = None,
    risk: str = "low",
    is_healthy: bool = True,
    recommended_crop: str | None = None,
    planted_crop: str | None = None,
    sensor_connected: bool = False,
    area_ha: float | None = None,
    raining: bool | None = None,
    lang: str | None = None,
) -> dict[str, Any]:
    """Compute the full ASI card (total, grade, band, sub-scores, contributions)."""
    weather = weather or {}
    if raining is None:
        raining = bool(weather.get("is_rainy_now"))

    lang = normalise(lang)
    w, w_why = water_subscore(soil_moisture_pct, irrigation_action, raining, lang)
    wx, wx_why = weather_subscore(weather, lang)
    d, d_why = disease_subscore(risk, is_healthy, lang)
    r, r_why = resource_subscore(risk, recommended_crop, planted_crop, sensor_connected, area_ha, lang)

    subs = {"water": w, "weather": wx, "disease": d, "resource": r}
    reasons = {"water": w_why, "weather": wx_why, "disease": d_why, "resource": r_why}
    contributions = {k: round(WEIGHTS[k] * v, 2) for k, v in subs.items()}
    total = round(sum(contributions.values()), 1)
    letter = grade_for(total)

    weakest = min(subs, key=lambda k: subs[k])
    tips = {
        "water": say("s_tip_water", lang),
        "weather": say("s_tip_weather", lang),
        "disease": say("s_tip_disease", lang),
        "resource": say("s_tip_resource", lang),
    }
    return {
        "total": total,
        "grade": letter,
        "band": BAND_LABEL[letter],
        "band_label": band_label(letter, lang),
        "subscores": {k: round(v, 1) for k, v in subs.items()},
        "weights": WEIGHTS,
        "contributions": contributions,
        "reasons": reasons,
        "weakest_area": weakest,
        "weakest_area_label": say(f"sub_{weakest}", lang) or weakest,
        "subscore_labels": {k: say(f"sub_{k}", lang) or k for k in subs},
        "top_tip": tips[weakest],
        "formula": "ASI = 0.30*water + 0.25*weather + 0.25*disease + 0.20*resource",
        "scale": say("s_scale", lang),
        "language": lang,
    }
