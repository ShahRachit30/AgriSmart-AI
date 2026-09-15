"""Orchestration layer: turn one leaf photo + a few numbers into one analysis.

Order of operations (each step degrades gracefully, never raises):
  1. prediction      (model/inference.py)          -> optional: may be None
  2. weather         (modules/weather.py)          -> falls back to manual values
  3. irrigation      (modules/weather.py)          -> always returns a decision
  4. risk + KB       (modules/recommendations.py)  -> only with a prediction
  5. sustainability  (modules/sustainability.py)   -> always
  6. crop advice     (modules/crop_recommendation.py) -> when NPK+climate present
  7. sensors         (modules/iot_sim.py)          -> simulated, labelled as such
  8. narrative       (plain-English summary + warnings for the UI banner)

Everything here is pure Python and offline-safe, which keeps the API testable
without a network and means a judge can run the whole app on a laptop.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from modules import crop_recommendation, iot_sim, recommendations, sustainability, weather as wx
from modules.app_phrases import say
from modules.assistant_i18n import localize_condition, localize_crop
from modules.i18n import normalise, t


def _narration(pred: dict | None, risk: dict | None, irr: dict | None, sus: dict | None,
               weather: dict | None, lang: str) -> str:
    """One-paragraph summary for the UI banner, in the requested language."""
    bits: list[str] = []
    if pred and risk:
        crop = localize_crop(risk.get("crop"), lang)
        if risk.get("is_healthy"):
            bits.append(say("n_healthy", lang, crop=crop or risk.get("crop"),
                            conf=f"{pred['confidence']:.0%}"))
        else:
            # "Tomato late blight (…) on Tomato" reads badly in every language - drop
            # the crop word when the condition name already begins with it.
            condition_txt = localize_condition(risk.get("condition"), lang) or ""
            crop_txt = crop if crop and not condition_txt.lower().startswith(str(crop).lower()) else ""
            bits.append(say("n_detected", lang, cond=condition_txt,
                            crop=(f" {crop_txt}" if crop_txt else ""),
                            conf=f"{pred['confidence']:.0%}",
                            risk=risk.get("risk_label")))
    elif pred is None:
        bits.append(say("n_no_photo", lang))
    if irr:
        reason = irr["reasons"][0] if irr.get("reasons") else say("n_see_reasons", lang)
        bits.append(say("n_irrigation", lang, action=irr.get("action_label"), reason=reason))
    if weather and weather.get("ok"):
        bits.append(say("n_weather", lang, cond=weather.get("condition"),
                        t=weather.get("temperature_c"), rain=weather.get("rain_probability_pct")))
    if sus:
        bits.append(say("n_index", lang, total=sus.get("total"), grade=sus.get("grade"),
                        weakest=sus.get("weakest_area")))
    if risk and risk.get("advisory_level") in ("act-now", "emergency"):
        bits.append(say("n_act_today", lang))
    return " ".join(b for b in bits if b)


def run_analysis(
    prediction: dict[str, Any] | None = None,
    soil_moisture_pct: float | None = None,
    soil_ph: float | None = None,
    city: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    weather_obj: dict[str, Any] | None = None,
    planted_crop: str | None = None,
    area_ha: float | None = None,
    crop_inputs: dict[str, Any] | None = None,
    language: str | None = None,
    include_sensors: bool = True,
    sensor_reading: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the complete analysis payload (see schemas.AnalysisResponse)."""
    lang = normalise(language)
    warnings: list[str] = []

    # 2. weather ---------------------------------------------------------- #
    if weather_obj is None:
        weather_obj = wx.fetch_weather(city=city, latitude=latitude, longitude=longitude, lang=lang)
    if isinstance(weather_obj, dict) and not weather_obj.get("ok"):
        warnings.append(t("weather_offline", lang))

    # 3. irrigation ------------------------------------------------------- #
    soil = soil_moisture_pct
    if soil is None and sensor_reading:
        soil = sensor_reading.get("soil_moisture_pct")
        if soil is not None:
            warnings.append("Soil moisture taken from the simulated sensor feed "
                            "(no manual reading supplied).")
    irrigation = wx.assess(weather_obj if isinstance(weather_obj, dict) else {}, soil, lang)
    et0 = wx.evapotranspiration_proxy(weather_obj or {})
    if et0:
        irrigation["et0_proxy_mm_day"] = et0

    # 4. risk + actions --------------------------------------------------- #
    risk = None
    actions: list[dict[str, Any]] = []
    if prediction:
        slug = prediction.get("class")
        risk = recommendations.assess_risk(slug, prediction.get("confidence", 0.0), weather_obj, lang)
        actions = recommendations.actions_for(slug, risk["risk"], lang)
        if prediction.get("confidence", 0) < recommendations.LOW_CONF:
            warnings.append(t("confidence_low", lang))

    # 6. crop recommendation ---------------------------------------------- #
    crop_rec = None
    if crop_inputs:
        try:
            crop_rec = crop_recommendation.from_soil_profile({**crop_inputs, "top_k": 3}, lang=lang)
        except ValueError as exc:
            warnings.append(f"{t('crop_rec_skipped', lang)}: {exc}")

    # 5. sustainability --------------------------------------------------- #
    sus = sustainability.index(
        soil_moisture_pct=soil,
        irrigation_action=irrigation.get("action"),
        weather=weather_obj if isinstance(weather_obj, dict) else {},
        risk=(risk or {}).get("risk", "low"),
        is_healthy=(risk or {}).get("is_healthy", True) if prediction else True,
        recommended_crop=(crop_rec or {}).get("top_crop"),
        planted_crop=planted_crop,
        sensor_connected=bool(sensor_reading) or include_sensors,
        area_ha=area_ha,
        lang=lang,
    )

    sensors = iot_sim.latest(lang=lang) if include_sensors else None
    if isinstance(sensors, dict):
        sensors["language"] = lang

    rec_block = None
    if risk:
        rec_block = {
            "symptoms": risk.get("symptoms", []),
            "organic_first": risk.get("organic_actions", []),
            "chemical_option": risk.get("chemical_option"),
            "prevention": risk.get("prevention", []),
            "advisory_level": risk.get("advisory_level"),
        }

    if isinstance(prediction, dict):
        # canonical slugs stay English (tests + the samples contract depend on them);
        # the display names are added alongside, in the requested language.
        prediction = {**prediction,
                      "condition_localized": localize_condition(prediction.get("condition"), lang),
                      "crop_localized": localize_crop(prediction.get("crop"), lang)}

    payload: dict[str, Any] = {
        "session_id": uuid.uuid4().hex[:12],
        "language": lang,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prediction": prediction,
        "risk": risk,
        "irrigation": irrigation,
        "weather": weather_obj,
        "sustainability": sus,
        "actions": actions,
        "recommendations": rec_block,
        "crop_recommendation": crop_rec,
        "sensors": sensors,
        "planted_crop": planted_crop,
        "area_ha": area_ha,
        "soil_ph": soil_ph,
        "warnings": warnings,
        "disclaimer": t("disclaimer", lang),
    }
    payload["narrative"] = _narration(prediction, risk, irrigation, sus, weather_obj, lang)
    return payload
