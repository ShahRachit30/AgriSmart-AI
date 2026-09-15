"""Bonus A - Crop recommendation (RandomForest, 22 crops).

Model: `model/crop_model.joblib` + `model/crop_label_encoder.joblib`, trained by
`scripts/train_crop_model.py` on the public Kaggle "Crop Recommendation Dataset"
(2,200 rows, CC0). Metrics land in `report/crop_metrics.json`.

Fallback: if joblib files are missing the module scores the inputs against
per-crop parameter envelopes (`ENVELOPES`, derived from the training data's
min/max) and returns the same response shape with ``engine="envelope-rules"``,
so the API never 503s on Bonus A.

Inputs (from the dataset): N, P, K (kg/ha), temperature (C), humidity (%),
ph, rainfall (mm). `from_soil_profile()` also accepts a farmer's soil-test card
and fills what it can.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .app_phrases import say
from .assistant_i18n import localize_crop
from .i18n import normalise

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "model" / "crop_model.joblib"
ENCODER_PATH = ROOT / "model" / "crop_label_encoder.joblib"
CENTROID_PATH = ROOT / "model" / "crop_centroids.json"
METRICS_PATH = ROOT / "report" / "crop_metrics.json"

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
UNITS = {"N": "kg/ha", "P": "kg/ha", "K": "kg/ha", "temperature": "C",
         "humidity": "%", "ph": "pH", "rainfall": "mm"}

# Ranges are the dataset's observed envelope per crop (used only by the fallback).
ENVELOPES: dict[str, dict[str, tuple[float, float]]] = {
    "rice": {"N": (60, 100), "P": (35, 60), "K": (35, 45), "temperature": (20, 27),
             "humidity": (80, 85), "ph": (5.5, 7), "rainfall": (180, 300)},
    "maize": {"N": (60, 120), "P": (35, 60), "K": (35, 45), "temperature": (18, 27),
              "humidity": (55, 75), "ph": (5.5, 7), "rainfall": (60, 110)},
    "chickpea": {"N": (20, 60), "P": (55, 80), "K": (75, 85), "temperature": (15, 22),
                 "humidity": (14, 25), "ph": (5.5, 9), "rainfall": (60, 100)},
    "kidneybeans": {"N": (20, 40), "P": (55, 80), "K": (15, 25), "temperature": (15, 25),
                    "humidity": (18, 25), "ph": (5.5, 6), "rainfall": (90, 150)},
    "pigeonpeas": {"N": (20, 40), "P": (55, 80), "K": (15, 25), "temperature": (18, 35),
                   "humidity": (40, 70), "ph": (4.5, 7), "rainfall": (90, 200)},
    "mothbeans": {"N": (20, 40), "P": (45, 65), "K": (15, 25), "temperature": (24, 32),
                  "humidity": (40, 65), "ph": (3.5, 10), "rainfall": (30, 75)},
    "mungbean": {"N": (20, 40), "P": (45, 65), "K": (15, 25), "temperature": (25, 35),
                 "humidity": (80, 90), "ph": (6, 7), "rainfall": (30, 60)},
    "blackgram": {"N": (20, 40), "P": (55, 80), "K": (15, 25), "temperature": (25, 35),
                  "humidity": (60, 70), "ph": (6, 8), "rainfall": (60, 75)},
    "lentil": {"N": (0, 40), "P": (55, 80), "K": (15, 25), "temperature": (18, 30),
               "humidity": (60, 70), "ph": (5.5, 8), "rainfall": (40, 50)},
    "pomegranate": {"N": (0, 40), "P": (5, 30), "K": (35, 45), "temperature": (18, 25),
                    "humidity": (85, 95), "ph": (5.5, 7), "rainfall": (100, 115)},
    "banana": {"N": (80, 120), "P": (70, 95), "K": (45, 55), "temperature": (25, 30),
               "humidity": (75, 85), "ph": (5.5, 7), "rainfall": (90, 120)},
    "mango": {"N": (0, 40), "P": (15, 40), "K": (25, 40), "temperature": (27, 36),
              "humidity": (45, 55), "ph": (4.5, 7), "rainfall": (90, 100)},
    "grapes": {"N": (0, 40), "P": (120, 145), "K": (195, 205), "temperature": (8, 42),
               "humidity": (80, 85), "ph": (5.5, 7), "rainfall": (65, 75)},
    "watermelon": {"N": (80, 120), "P": (5, 30), "K": (45, 55), "temperature": (24, 27),
                   "humidity": (80, 90), "ph": (6, 7), "rainfall": (40, 60)},
    "muskmelon": {"N": (80, 120), "P": (5, 30), "K": (45, 55), "temperature": (27, 30),
                  "humidity": (90, 95), "ph": (6, 7), "rainfall": (20, 30)},
    "apple": {"N": (0, 40), "P": (120, 145), "K": (195, 205), "temperature": (21, 24),
              "humidity": (90, 95), "ph": (5.5, 6.5), "rainfall": (100, 130)},
    "orange": {"N": (0, 40), "P": (5, 30), "K": (5, 15), "temperature": (10, 35),
               "humidity": (90, 95), "ph": (6, 8), "rainfall": (100, 120)},
    "papaya": {"N": (30, 70), "P": (45, 70), "K": (45, 55), "temperature": (23, 45),
               "humidity": (90, 95), "ph": (6.5, 7), "rainfall": (40, 250)},
    "coconut": {"N": (0, 40), "P": (5, 30), "K": (25, 35), "temperature": (25, 30),
                "humidity": (90, 99), "ph": (5, 6.5), "rainfall": (130, 230)},
    "cotton": {"N": (100, 140), "P": (40, 60), "K": (15, 25), "temperature": (22, 27),
               "humidity": (75, 85), "ph": (5.5, 8), "rainfall": (60, 110)},
    "jute": {"N": (60, 100), "P": (35, 60), "K": (35, 45), "temperature": (23, 27),
             "humidity": (70, 90), "ph": (6, 7), "rainfall": (150, 200)},
    "coffee": {"N": (80, 120), "P": (15, 40), "K": (25, 35), "temperature": (23, 28),
               "humidity": (50, 70), "ph": (6, 7.5), "rainfall": (150, 200)},
}

CROP_NOTES = {
    "rice": "Needs standing water or assured irrigation; kharif staple for high-rainfall belts.",
    "maize": "Versatile kharif/rabi cereal; fits your rainfall window with 60-110 mm.",
    "wheat": "Rabi cereal; sow after the monsoon retreats.",
    "chickpea": "Rabi pulse that fixes nitrogen - good after a cereal.",
    "cotton": "Long-duration cash crop; needs 100+ kg/ha N and warm nights.",
    "grapes": "High K demand (200 kg/ha); best with drip + fertigation.",
    "banana": "Heavy feeder; 80-120 kg/ha N with assured irrigation.",
    "mango": "Perennial; tolerates a wide pH band, needs a dry spell to flower.",
    "coffee": "Shade crop for 150-200 mm rainfall belts with mild temperatures.",
    "coconut": "Perennial for coastal humid belts (RH 90 %+).",
}
# crop -> the phrase row that carries its note in all three languages
NOTE_KEYS = {crop: f"c_{key}" for crop, key in {
    "rice": "rice", "maize": "maize", "wheat": "wheat", "chickpea": "pulse", "cotton": "cash",
    "grapes": "highk", "banana": "heavy", "mango": "perennial", "coffee": "shade",
    "coconut": "coastal",
}.items()}

_CACHE: dict[str, Any] = {}


def _load() -> tuple[Any, Any] | tuple[None, None]:
    if "model" in _CACHE:
        return _CACHE["model"], _CACHE["encoder"]
    model = enc = None
    if MODEL_PATH.exists() and ENCODER_PATH.exists():
        try:
            import joblib
            model = joblib.load(MODEL_PATH)
            enc = joblib.load(ENCODER_PATH)
        except Exception:
            model = enc = None
    _CACHE["model"], _CACHE["encoder"] = model, enc
    return model, enc


def model_available() -> bool:
    m, e = _load()
    return m is not None and e is not None


def metrics() -> dict[str, Any] | None:
    if METRICS_PATH.exists():
        try:
            return json.loads(METRICS_PATH.read_text())
        except Exception:
            return None
    return None


def _clean(values: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for f in FEATURES:
        v = values.get(f, values.get(f.lower()))
        try:
            out[f] = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"missing or non-numeric input '{f}' ({UNITS[f]})")
    return out


def _envelope_scores(x: dict[str, float]) -> list[tuple[str, float]]:
    """Fallback scorer: Gaussian-ish membership of each crop's parameter envelope."""
    scores: list[tuple[str, float]] = []
    for crop, env in ENVELOPES.items():
        s, n = 0.0, 0
        for f, (lo, hi) in env.items():
            v = x[f]
            mid, half = (lo + hi) / 2, max((hi - lo) / 2, 1e-6)
            d = abs(v - mid) / (half * 1.6)
            s += 1.0 / (1.0 + d * d)
            n += 1
        scores.append((crop, s / max(n, 1)))
    scores.sort(key=lambda kv: -kv[1])
    total = sum(s for _, s in scores) or 1.0
    return [(c, round(s / total, 4)) for c, s in scores]


def recommend(values: dict[str, Any], top_k: int = 3, lang: str | None = None) -> dict[str, Any]:
    """Rank crops for a soil/climate reading. Raises ValueError on bad input."""
    langs = normalise(lang)
    x = _clean(values)
    model, enc = _load()
    engine = "RandomForest(200 trees)"
    if model is not None and enc is not None:
        row = [[x[f] for f in FEATURES]]
        proba = model.predict_proba(row)[0]
        idx = proba.argsort()[::-1][:top_k]
        recs = [{"crop": str(enc.inverse_transform([i])[0]),
                 "probability": round(float(proba[i]), 4)} for i in idx]
    else:
        engine = say("c_rules", langs)
        recs = [{"crop": c, "probability": p} for c, p in _envelope_scores(x)[:top_k]]

    for r in recs:
        key = NOTE_KEYS.get(r["crop"])
        r["note"] = say(key, langs) if key else say("c_envelope", langs)
        r["crop_localized"] = localize_crop(r["crop"], langs)
    top = recs[0] if recs else {"crop": None, "probability": 0.0}
    return {
        "engine": engine,
        "model_available": model_available(),
        "inputs": x,
        "units": UNITS,
        "recommendations": recs,
        "top_crop": top["crop"],
        "top_crop_localized": localize_crop(top["crop"], langs),
        "top_probability": top["probability"],
        "confidence_band": ("high" if top["probability"] >= 0.6 else
                            "medium" if top["probability"] >= 0.35 else "low"),
        "advice": say("c_advice", langs,
                      crop=localize_crop(top["crop"], langs) or str(top["crop"]).title()),
        "language": langs,
        "metrics": metrics(),
    }


def from_soil_profile(profile: dict[str, Any], top_k: int = 3,
                      lang: str | None = None) -> dict[str, Any]:
    """Accept a farmer-friendly soil card (aliases) and delegate to `recommend`."""
    alias = {
        "nitrogen": "N", "n": "N", "phosphorus": "P", "p": "P", "potassium": "K", "k": "K",
        "temp": "temperature", "t": "temperature", "air_temperature": "temperature",
        "rh": "humidity", "humidity_pct": "humidity", "ph_value": "ph", "soil_ph": "ph",
        "rain": "rainfall", "rain_mm": "rainfall", "rainfall_mm": "rainfall",
    }
    merged: dict[str, Any] = {}
    for key, val in (profile or {}).items():
        k = str(key).strip().lower()
        merged[alias.get(k, k)] = val
    return recommend(merged, top_k=top_k, lang=lang)


def sample_inputs() -> dict[str, float]:
    """A neutral demo reading (mean of the dataset) for the UI's 'use sample' button."""
    return {"N": 50.55, "P": 53.36, "K": 48.15, "temperature": 25.62,
            "humidity": 71.48, "ph": 6.47, "rainfall": 103.46}
