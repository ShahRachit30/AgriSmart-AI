"""AgriSmart AI - FastAPI backend.

Run:
    python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000

Endpoints
---------
GET  /api/health              service + model status
GET  /api/meta                classes, thresholds, formulas, dataset provenance
POST /api/predict             multipart image -> prediction + top-3
POST /api/analyze             image + field context -> full analysis (one call for the UI)
POST /api/assistant           grounded Q&A over a context (optional LLM if a key is set)
POST /api/weather             city/coords -> live Open-Meteo data + irrigation advice
POST /api/recommend-crop      NPK + climate -> top-3 crops (Bonus A)
GET  /api/sensors/latest      simulated node reading        (Bonus F)
GET  /api/sensors/history     last N simulated samples
GET  /api/sensors/devices     simulated node inventory
POST /api/sensors/ingest      firmware contract for a REAL node
GET  /api/metrics             field-test metrics from report/metrics.json
GET  /                        the built React UI (with SPA fallback)

Error policy (FR-10): every failure returns JSON with a human message, never a
stack trace. Invalid image -> 415, bad numbers -> 422, missing model -> 503.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from modules.env import env_path, load_env, mask

load_env()          # `.env` (git-ignored) next to run.sh; real env vars win

from app.backend.analysis import run_analysis
from app.backend.schemas import (AssistantRequest, CropRecommendationRequest, HealthResponse,
                                 RelocalizeRequest, SensorIngestRequest, SoilProfileRequest,
                                 WeatherRequest)
from model.inference import get_classifier
from modules import assistant as assistant_mod
from modules import imaging
from modules import crop_recommendation, iot_sim
from modules import weather as weather_mod
from modules.app_phrases import say
from modules.i18n import LANGS, normalise, t
from modules import recommendations
from modules.recommendations import KB, actions_for, assess_risk

ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
REPORT_DIR = ROOT / "report"
SAMPLES_DIR = ROOT / "samples"
APP_VERSION = "1.1.2"
START_TIME = time.time()
# Written by `npm run build` into app/backend/static/BUILD_ID.txt - a human-visible
# stamp so "am I looking at the new build?" is answerable without guessing.
BUILD_ID = (STATIC_DIR / "BUILD_ID.txt").read_text().strip() \
    if (STATIC_DIR / "BUILD_ID.txt").exists() else os.getenv("AGRI_BUILD_ID", "dev")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB; the client also downscales before upload

# --------------------------------------------------------------- sessions --
# An analysis is expensive (4 model forwards + a weather fetch) but its *content*
# is a pure function of (prediction, inputs, language). To let the UI switch
# language instantly we keep the language-neutral inputs of the last few analyses
# and re-render them on demand - no model run, no network.
_SESSIONS: dict[str, dict[str, Any]] = {}
SESSION_LIMIT = 32            # newest wins; a demo never needs more
SESSION_TTL_S = 6 * 3600


def remember_session(payload: dict[str, Any], inputs: dict[str, Any]) -> None:
    """Store the re-usable parts of an analysis under its session_id."""
    sid = payload.get("session_id")
    if not sid:
        return
    prediction = payload.get("prediction")
    _SESSIONS[sid] = {
        "inputs": dict(inputs),
        "prediction": dict(prediction) if isinstance(prediction, dict) else None,
        "ts": time.time(),
        "language": payload.get("language"),
    }
    # prune: expired first, then oldest over the cap
    now = time.time()
    for key in [k for k, v in _SESSIONS.items() if now - v["ts"] > SESSION_TTL_S]:
        _SESSIONS.pop(key, None)
    while len(_SESSIONS) > SESSION_LIMIT:
        oldest = min(_SESSIONS, key=lambda k: _SESSIONS[k]["ts"])
        _SESSIONS.pop(oldest, None)


_SAMPLE_INDEX: dict[str, dict[str, Any]] = {}
_SAMPLE_INDEX_STAMP: float | None = None


def sample_index(force: bool = False) -> dict[str, dict[str, Any]]:
    """Bundled demo photos, keyed by id, from samples/manifest.json.

    Only files that appear in the manifest and resolve *inside* samples/ are
    served, so these endpoints cannot be used to read arbitrary paths.

    The index is cached but re-read whenever manifest.json changes on disk, so
    re-running scripts/curate_samples.py takes effect without a server restart.
    """
    global _SAMPLE_INDEX, _SAMPLE_INDEX_STAMP
    manifest = SAMPLES_DIR / "manifest.json"
    if not manifest.exists():
        _SAMPLE_INDEX, _SAMPLE_INDEX_STAMP = {}, None
        return _SAMPLE_INDEX
    try:
        stamp = manifest.stat().st_mtime
    except OSError:
        stamp = None
    if _SAMPLE_INDEX and not force and stamp == _SAMPLE_INDEX_STAMP:
        return _SAMPLE_INDEX
    try:
        rows = json.loads(manifest.read_text())
    except Exception:
        return _SAMPLE_INDEX
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        rel = Path(str(row.get("file", "")))
        abs_path = (ROOT / rel).resolve()
        if not str(abs_path).startswith(str(SAMPLES_DIR.resolve())) or not abs_path.exists():
            continue
        index[rel.stem] = {**row, "id": rel.stem, "abs_path": str(abs_path)}
    _SAMPLE_INDEX, _SAMPLE_INDEX_STAMP = index, stamp
    return _SAMPLE_INDEX

app = FastAPI(
    title="AgriSmart AI API",
    version=APP_VERSION,
    description="Crop-disease detection + irrigation/weather/sustainability/crop/AI advisories "
                "for smallholder farmers.",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    allow_credentials=False,
)


@app.middleware("http")
async def _cache_policy(request: Request, call_next):
    """Stop browsers from pinning an old UI after a rebuild.

    * ``/assets/*``  - Vite emits content-hashed filenames, so they are immutable
      and can be cached hard.
    * everything else (HTML entry point, API, sample images) - must revalidate,
      otherwise a rebuilt bundle is invisible until the user clears their cache.
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# --------------------------------------------------------------------------- #
# friendly error handling (FR-10)                                             #
# --------------------------------------------------------------------------- #
@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    problems = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query"))
        problems.append(f"{loc or 'request'}: {err.get('msg', 'invalid value')}")
    return JSONResponse(status_code=422, content={
        "ok": False, "error": "invalid_request", "message": "Some values are missing or out of range.",
        "details": problems,
        "hint": "Check the highlighted fields - every value needs to be a number inside its "
                "normal range (see /docs for the limits).",
    })


@app.exception_handler(StarletteHTTPException)
async def _starlette_http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Any 404/405 (including unknown /api/* routes) becomes a friendly JSON body."""
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    if exc.status_code == 404:
        return JSONResponse(status_code=404, content={
            "ok": False, "error": "not_found",
            "message": f"No route '{request.url.path}'.",
            "hint": "API endpoints are listed at /api/meta; interactive docs at /docs.",
        })
    if exc.status_code == 405:
        return JSONResponse(status_code=405, content={
            "ok": False, "error": "method_not_allowed",
            "message": f"{request.method} is not allowed on {request.url.path}.",
            "hint": "See /docs for the methods each endpoint accepts.",
        })
    return JSONResponse(status_code=exc.status_code, content={
        "ok": False, "error": "http_error", "message": str(exc.detail),
    })


@app.exception_handler(HTTPException)
async def _http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(status_code=exc.status_code, content={
        "ok": False, "error": "http_error", "message": str(detail),
    })


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
    return JSONResponse(status_code=500, content={
        "ok": False, "error": "internal_error",
        "message": "Something went wrong on our side. Nothing was charged and no data was lost - "
                   "please retry, and if it persists restart the server.",
        "detail": f"{type(exc).__name__}",
    })


def _lang(value: str | None) -> str:
    return normalise(value)


def _predict_from_upload(data: bytes, filename: str) -> dict[str, Any]:
    clf = get_classifier()
    if not clf.available:
        raise HTTPException(status_code=503, detail={
            "ok": False, "error": "model_unavailable", "message": t("model_unavailable"),
            "detail": clf.load_error,
            "hint": "Train the model (python model/train.py --data data/splits --model resnet18 "
                    "--img-size 192 --epochs 8 --batch-size 64) or drop a best_model.pth into model/.",
        })
    try:
        return clf.predict_bytes(data, filename)
    except ValueError as exc:
        raise upload_error(415, "invalid_image", t("upload_invalid"),
                           detail=f"{filename}: {exc}")


def upload_capabilities() -> dict[str, Any]:
    """What this server can actually decode, plus the size it will accept.

    Published on /api/health and /api/meta so a client (or a judge with curl) can
    tell why an upload would fail *before* sending 20 MB over a field connection.
    """
    return {**imaging.capabilities(), "max_mb": MAX_UPLOAD_BYTES // (1024 * 1024)}


def upload_help(action: str = "Use a JPG, PNG, WebP, BMP, TIFF or HEIC photo.") -> str:
    """The one-line fix shown to the user when a photo cannot be analysed."""
    if not imaging.HEIF_OK:
        return (f"{action} If the file came from an iPhone, this server reports "
                f"heic_supported=false - export it as JPEG first.")
    return action


def upload_error(status: int, error: str, message: str, detail: str = "",
                 **extra: Any) -> HTTPException:
    """Every upload failure answers with the same flat, actionable shape.

    The React client renders `message` in the banner and `hint` underneath it, so
    all upload errors carry both - plus the machine-readable limits, which is what
    makes "why did my photo fail?" answerable from `curl` alone.
    """
    body: dict[str, Any] = {
        "ok": False, "error": error, "message": message,
        "accepted": upload_capabilities()["extensions"],
        "heic_supported": imaging.HEIF_OK,
        "max_mb": upload_capabilities()["max_mb"],
        "hint": upload_help(),
    }
    if detail:
        body["detail"] = detail
    body.update(extra)
    return HTTPException(status_code=status, detail=body)


async def _read_image(image: UploadFile | None) -> tuple[bytes | None, str]:
    """Read an upload. The *bytes* decide whether it is an image, not the filename.

    A valid JPEG saved as `photo` or `leaf.unknown` used to be rejected on the
    suffix alone - that is now impossible; only genuinely undecodable data fails,
    and it fails in `_predict_from_upload` with a message that says what to do.
    """
    if image is None:
        return None, ""
    name = image.filename or "upload.jpg"
    data = await image.read()
    if not data:
        raise upload_error(
            415, "invalid_image", t("upload_invalid"),
            detail=f"the uploaded file '{name}' arrived empty (0 bytes)",
            hint="The transfer was interrupted - please pick the photo again.",
        )
    if len(data) > MAX_UPLOAD_BYTES:
        mb = len(data) / (1024 * 1024)
        raise upload_error(
            413, "image_too_large",
            f"Image is {mb:.1f} MB, which is over the {upload_capabilities()['max_mb']} MB limit. "
            f"Please compress it or take the photo at a lower resolution.",
            detail=f"received {mb:.1f} MB, limit {upload_capabilities()['max_mb']} MB",
            received_mb=round(mb, 2),
            hint="Most phone cameras can be set to a smaller photo size; any photo under the "
                 "limit is downscaled automatically on the server.",
        )
    return data, name


# --------------------------------------------------------------------------- #
# meta                                                                        #
# --------------------------------------------------------------------------- #
@app.get("/api/health", response_model=HealthResponse)
def health() -> dict[str, Any]:
    clf = get_classifier()
    return {
        "status": "ok", "version": APP_VERSION, "build_id": BUILD_ID,
        "model_available": clf.available,
        "model": clf.info(), "uptime_s": round(time.time() - START_TIME, 1),
        "demo_mode": not clf.available,
        "uploads": upload_capabilities(),
        # which assistant engine is live - a key is never echoed, only its presence
        "assistant": assistant_mod.llm_status(),
    }


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    """Everything a judge/UI needs to reproduce the numbers."""
    from model.dataset import IMAGENET_MEAN, IMAGENET_STD
    clf = get_classifier()
    thresholds = {
        "irrigation": {
            "rain_delay_pct": weather_mod.RAIN_DELAY_PCT,
            "rain_monitor_pct": weather_mod.RAIN_MONITOR_PCT,
            "soil_dry_pct": weather_mod.SOIL_DRY_PCT,
            "soil_target_pct": weather_mod.SOIL_TARGET_PCT,
            "heat_stress_c": weather_mod.HEAT_STRESS_C,
            "frost_c": weather_mod.FROST_C,
            "humid_disease_pct": weather_mod.HUMID_DISEASE_PCT,
        },
        "risk": {"kb_severity_conf": 0.75, "low_conf": 0.50},
        "sustainability": {"weights": {"water": 0.30, "weather": 0.25, "disease": 0.25,
                                       "resource": 0.20},
                           "grades": "A>=80 B>=65 C>=50 D>=35 E<35"},
    }
    return {
        "app": "AgriSmart AI", "version": APP_VERSION, "build_id": BUILD_ID,
        "languages": list(LANGS),
        "classes": clf.classes,
        "n_classes": len(clf.classes) or 18,
        "model": clf.info(),
        "thresholds": thresholds,
        "kb_classes": sorted(KB.keys()),
        "uploads": upload_capabilities(),
        "normalisation": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
        "datasets": {
            "train_val": "PlantVillage (HuggingFace mirror dpdl-benchmark/plant_village) - CC-BY",
            "field_test": "PlantDoc (pratikkayal/PlantDoc-Dataset) - MIT, never trained on",
            "crop_recommendation": "Kaggle Crop Recommendation Dataset (mirror randalakab/"
                                   "Crop-recommendation) - CC0",
            "weather": "Open-Meteo (free tier, no key)",
        },
        "endpoints": ["/api/health", "/api/meta", "/api/predict", "/api/analyze",
                      "/api/assistant", "/api/weather", "/api/recommend-crop",
                      "/api/sensors/latest", "/api/sensors/history", "/api/sensors/devices",
                      "/api/sensors/ingest", "/api/metrics"],
        "assistant": {**assistant_mod.llm_status(),
                      "providers_supported": ["groq", "openai", "gemini"],
                      "note": "Optional: drop GROQ_API_KEY (or OPENAI_API_KEY / GEMINI_API_KEY) "
                              "into .env and restart. Without a key the deterministic grounded "
                              "engine answers - no hallucinations, no network dependency."},
    }


@app.get("/api/metrics")
def metrics(language: str = "en") -> dict[str, Any]:
    """Held-out field-test metrics (report/metrics.json), with lab metrics if present."""
    out: dict[str, Any] = {"ok": True, "available": False}
    field = REPORT_DIR / "metrics.json"
    lab = REPORT_DIR / "metrics_val.json"
    for key, path in (("field_test", field), ("lab_val", lab)):
        if path.exists():
            try:
                out[key] = json.loads(path.read_text())
                out["available"] = True
            except Exception as exc:
                out[key] = {"error": f"could not parse {path.name}: {exc}"}
    crop = REPORT_DIR / "crop_metrics.json"
    if crop.exists():
        try:
            out["crop_recommendation"] = json.loads(crop.read_text())
        except Exception:
            pass
    if out["available"]:
        f = out.get("field_test") or {}
        out["summary"] = {
            "field_macro_f1": f.get("macro_f1"),
            "field_accuracy": f.get("accuracy"),
            "field_top3_accuracy": f.get("top3_accuracy"),
            "field_n_images": f.get("n_images"),
            "note": say("md_field_note", _lang(language)),
        }
    return out


# --------------------------------------------------------------------------- #
# bundled demo samples (so the app can be tried without any dataset download)  #
# --------------------------------------------------------------------------- #
@app.get("/api/samples")
def samples_list(kind: str | None = None, language: str = "en") -> dict[str, Any]:
    """Verified field photos shipped with the repo, with their expected output.

    `true_class`/`model_says` stay as the canonical slugs the tests and manifest use;
    the `_label` fields next to them are the display names in `language`.
    """
    lang = _lang(language)
    idx = sample_index()
    rows = [v for v in idx.values() if kind is None or v.get("kind") == kind]
    def label(slug: str | None) -> str | None:
        if not slug:
            return None
        return recommendations.condition_name(slug, lang)
    return {
        "ok": True, "count": len(rows), "language": lang,
        "note": t("samples_note", lang),
        "samples": [{
            "id": r["id"], "kind": r.get("kind"), "true_class": r.get("true"),
            "model_says": r.get("model_says"), "confidence": r.get("confidence"),
            "correct": r.get("correct"), "image_url": f"/api/samples/{r['id']}/image",
            "true_class_label": label(r.get("true")), "model_says_label": label(r.get("model_says")),
        } for r in sorted(rows, key=lambda r: (r.get("kind") != "right", r.get("true", "")))],
    }


@app.get("/api/samples/{sample_id}/image")
def sample_image(sample_id: str) -> FileResponse:
    entry = sample_index().get(sample_id)
    if entry is None:
        raise HTTPException(status_code=404, detail={
            "ok": False, "error": "sample_not_found",
            "message": f"No bundled sample '{sample_id}'.",
            "hint": "List them at GET /api/samples.",
        })
    path = Path(entry["abs_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail={
            "ok": False, "error": "sample_file_missing",
            "message": "This sample file is no longer on disk.",
            "hint": "Re-generate the demo set with `python scripts/curate_samples.py`.",
        })
    return FileResponse(str(path), media_type="image/jpeg", filename=path.name)


# --------------------------------------------------------------------------- #
# prediction + analysis                                                       #
# --------------------------------------------------------------------------- #
@app.post("/api/predict")
async def predict_endpoint(image: UploadFile = File(...), language: str = Form("en")):
    data, name = await _read_image(image)
    result = _predict_from_upload(data, name)
    lang = _lang(language)
    risk = assess_risk(result["class"], result["confidence"], None, lang)
    return {
        "ok": True,
        "prediction": result,
        "risk": risk,
        "actions": actions_for(result["class"], risk["risk"], lang),
        "disclaimer": t("disclaimer", lang),
    }


@app.post("/api/analyze")
async def analyze_endpoint(
    image: UploadFile | None = File(None),
    sample_id: str | None = Form(None),
    language: str = Form("en"),
    soil_moisture_pct: float | None = Form(None),
    soil_ph: float | None = Form(None),
    city: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    planted_crop: str | None = Form(None),
    area_ha: float | None = Form(None),
    nitrogen: float | None = Form(None),
    phosphorus: float | None = Form(None),
    potassium: float | None = Form(None),
    temperature: float | None = Form(None),
    humidity: float | None = Form(None),
    rainfall: float | None = Form(None),
    use_sensors: bool = Form(True),
):
    """One call for the whole dashboard: photo + numbers -> complete analysis."""
    lang = _lang(language)
    if soil_moisture_pct is not None and not 0 <= soil_moisture_pct <= 100:
        raise HTTPException(status_code=422, detail={
            "ok": False, "error": "invalid_request",
            "message": "soil_moisture_pct must be between 0 and 100.",
        })
    if soil_ph is not None and not 0 <= soil_ph <= 14:
        raise HTTPException(status_code=422, detail={
            "ok": False, "error": "invalid_request", "message": "soil_ph must be between 0 and 14.",
        })

    prediction = None
    if image is not None:
        data, name = await _read_image(image)
        if data:
            prediction = _predict_from_upload(data, name)
    elif sample_id:
        entry = sample_index().get(sample_id)
        if entry is None:
            raise HTTPException(status_code=404, detail={
                "ok": False, "error": "sample_not_found",
                "message": f"No bundled sample '{sample_id}'.",
                "hint": "List them at GET /api/samples.",
            })
        path = Path(entry["abs_path"])
        if not path.exists():
            raise HTTPException(status_code=404, detail={
                "ok": False, "error": "sample_file_missing",
                "message": "This sample file is no longer on disk.",
                "hint": "Re-generate the demo set with `python scripts/curate_samples.py`.",
            })
        prediction = _predict_from_upload(path.read_bytes(), path.name)
        prediction["source_name"] = path.name
        prediction["sample_id"] = sample_id

    crop_inputs = None
    if all(v is not None for v in (nitrogen, phosphorus, potassium, temperature, humidity, rainfall)) \
            and soil_ph is not None:
        crop_inputs = {"N": nitrogen, "P": phosphorus, "K": potassium, "temperature": temperature,
                       "humidity": humidity, "ph": soil_ph, "rainfall": rainfall}

    return _analyze_and_remember(
        prediction=prediction, soil_moisture_pct=soil_moisture_pct, soil_ph=soil_ph,
        city=city, latitude=latitude, longitude=longitude, planted_crop=planted_crop,
        area_ha=area_ha, crop_inputs=crop_inputs, language=lang,
        include_sensors=use_sensors, sensor_reading=None,   # fetched in-language below
    )


def _analyze_and_remember(**kwargs: Any) -> dict[str, Any]:
    """Run the analysis and remember the parts that are language-independent.

    `prediction` is the raw model output (slugs, confidence, English label), which
    never changes with language - so re-rendering it in another language is exact,
    not an approximation.
    """
    if kwargs.get("include_sensors"):
        kwargs["sensor_reading"] = iot_sim.latest(lang=kwargs.get("language"))
    payload = run_analysis(**kwargs)
    crop_inputs = kwargs.get("crop_inputs")
    if crop_inputs is None and all(kwargs.get(f) is not None for f in ("N",)):
        crop_inputs = None
    remember_session(payload, {
        "soil_moisture_pct": kwargs.get("soil_moisture_pct"),
        "soil_ph": kwargs.get("soil_ph"),
        "city": kwargs.get("city"),
        "latitude": kwargs.get("latitude"),
        "longitude": kwargs.get("longitude"),
        "planted_crop": kwargs.get("planted_crop"),
        "area_ha": kwargs.get("area_ha"),
        "crop_inputs": kwargs.get("crop_inputs"),
        "include_sensors": bool(kwargs.get("include_sensors")),
    })
    return payload


@app.post("/api/relocalize")
def relocalize_endpoint(req: RelocalizeRequest) -> dict[str, Any]:
    """Re-render a finished analysis in another language.

    The model is *not* re-run: the stored prediction is replayed through the same
    orchestration with a new language, so the numbers a farmer just read do not
    change when they tap the language selector - only the words do.
    """
    entry = _SESSIONS.get(req.session_id)
    lang = _lang(req.language)
    if entry is None:
        return {
            "ok": False, "error": "session_expired",
            "message": "That analysis is no longer cached on the server.",
            "hint": "Press Analyze again (or pick a sample) to redo it in the new language.",
            "language": lang,
        }
    inputs = dict(entry["inputs"])
    sensor = iot_sim.latest(lang=lang) if inputs.get("include_sensors") else None
    payload = run_analysis(prediction=entry["prediction"], language=lang,
                           sensor_reading=sensor, **inputs)
    # Keep the SAME session id: the browser keys its next language switch on it, so a
    # fresh id here would make the second switch look like an expired session.
    payload["session_id"] = req.session_id
    entry["language"] = lang
    entry["ts"] = time.time()
    return {"ok": True, "cached": True, **payload}


# --------------------------------------------------------------------------- #
# advisories                                                                  #
# --------------------------------------------------------------------------- #
@app.post("/api/assistant")
def assistant_endpoint(req: AssistantRequest) -> dict[str, Any]:
    out = assistant_mod.answer(req.question, req.context, req.language, allow_llm=req.allow_llm)
    return {"ok": True, **out}


@app.post("/api/weather")
def weather_endpoint(req: WeatherRequest) -> dict[str, Any]:
    data = weather_mod.fetch_weather(city=req.city, latitude=req.latitude, longitude=req.longitude)
    if not data.get("ok"):
        return {"ok": False, "error": "weather_unavailable", "message": t("weather_offline",
                                                                          req.language),
                "detail": data.get("error"), "weather": data,
                "hint": "Pass latitude/longitude directly, or keep using your manual soil "
                        "readings - the analysis works offline."}
    data["irrigation"] = weather_mod.assess(data, None, req.language)
    data["et0_proxy_mm_day"] = weather_mod.evapotranspiration_proxy(data)
    return {"ok": True, "weather": data, "irrigation": data["irrigation"]}


@app.post("/api/recommend-crop")
def recommend_crop_endpoint(req: CropRecommendationRequest) -> dict[str, Any]:
    try:
        out = crop_recommendation.recommend(req.model_dump(), top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "ok": False, "error": "invalid_request", "message": str(exc),
            "hint": "Send N, P, K (kg/ha), temperature (C), humidity (%), ph and rainfall (mm) "
                    "as numbers.",
        })
    return {"ok": True, **out}


@app.post("/api/recommend-crop/soil-profile")
def recommend_from_soil_profile(req: SoilProfileRequest) -> dict[str, Any]:
    payload = {k: v for k, v in req.model_dump().items() if v is not None and k != "top_k"}
    try:
        out = crop_recommendation.from_soil_profile(payload, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "ok": False, "error": "invalid_request", "message": f"soil card incomplete: {exc}",
            "hint": "A soil-test card usually has N, P, K, pH, rainfall and the local temperature "
                    "and humidity - send whatever you have and fill the rest.",
        })
    return {"ok": True, **out}


# --------------------------------------------------------------------------- #
# simulated IoT (Bonus F)                                                     #
# --------------------------------------------------------------------------- #
@app.get("/api/sensors/latest")
def sensors_latest(device_id: str = iot_sim.DEFAULT_DEVICE, language: str = "en") -> dict[str, Any]:
    return {"ok": True, **iot_sim.latest(device_id, lang=_lang(language))}


@app.get("/api/sensors/history")
def sensors_history(device_id: str = iot_sim.DEFAULT_DEVICE, samples: int = 24,
                    language: str = "en") -> dict[str, Any]:
    return {"ok": True, **iot_sim.history(device_id, samples, lang=_lang(language))}


@app.get("/api/sensors/devices")
def sensors_devices(language: str = "en") -> dict[str, Any]:
    return {"ok": True, "devices": iot_sim.devices(), "default": iot_sim.DEFAULT_DEVICE,
            "simulated": True, "note": t("devices_note", _lang(language))}


@app.post("/api/sensors/ingest")
def sensors_ingest(req: SensorIngestRequest) -> dict[str, Any]:
    try:
        return {"ok": True, **iot_sim.ingest(req.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "ok": False, "error": "invalid_request", "message": str(exc),
            "hint": "Send device_id, soil_moisture_pct (0-100) and temperature_c (-20..70) - "
                    "see modules/iot_sim.py for the full firmware contract.",
        })


# --------------------------------------------------------------------------- #
# static frontend (built React app lives in app/backend/static)                #
# --------------------------------------------------------------------------- #
if STATIC_DIR.is_dir():
    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):  # noqa: ANN202
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail={
                "ok": False, "error": "not_found", "message": f"No API route /{full_path}.",
            })
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(str(index),
                               headers={"Cache-Control": "no-store, no-cache, "
                                                        "must-revalidate, max-age=0"})
        raise HTTPException(status_code=404, detail={
            "ok": False, "error": "frontend_missing",
            "message": "Frontend build not found. Run: cd app/frontend && npm install && npm run build",
        })
else:
    @app.get("/", include_in_schema=False)
    def root_no_ui() -> dict[str, Any]:
        return {
            "ok": True, "app": "AgriSmart AI", "version": APP_VERSION,
            "message": "API is running, but the frontend bundle is not built yet.",
            "build": "cd app/frontend && npm install && npm run build",
            "docs": "/docs", "health": "/api/health",
        }


def _demo() -> None:  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    _demo()
