"""Pydantic request/response models for the AgriSmart API.

Validation is deliberately *friendly*: out-of-range values raise a 422 whose
detail string tells the farmer what to fix (FR-10 - no stack traces, ever).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Lang = Literal["en", "hi", "gu"]


class WeatherRequest(BaseModel):
    city: str | None = Field(None, description="City name, e.g. 'Ahmedabad'")
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    language: Lang = "en"

    @field_validator("city")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v


class WeatherResponse(BaseModel):
    ok: bool
    source: str
    city: str | None = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    condition: str | None = None
    rain_probability_pct: float | None = None
    daily: list[dict[str, Any]] = []
    error: str | None = None
    note: str | None = None


class CropRecommendationRequest(BaseModel):
    N: float = Field(..., ge=0, le=300, description="Nitrogen kg/ha")
    P: float = Field(..., ge=0, le=200, description="Phosphorus kg/ha")
    K: float = Field(..., ge=0, le=300, description="Potassium kg/ha")
    temperature: float = Field(..., ge=-10, le=60, description="Mean temperature C")
    humidity: float = Field(..., ge=0, le=100, description="Relative humidity %")
    ph: float = Field(..., ge=0, le=14, description="Soil pH")
    rainfall: float = Field(..., ge=0, le=1000, description="Rainfall mm")
    top_k: int = Field(3, ge=1, le=22)
    language: Lang = "en"


class SoilProfileRequest(BaseModel):
    """Farmer-friendly aliases are accepted by modules.crop_recommendation.from_soil_profile."""

    nitrogen: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    ph: float | None = None
    rainfall: float | None = None
    top_k: int = Field(3, ge=1, le=22)
    language: Lang = "en"


class RelocalizeRequest(BaseModel):
    """Re-render a finished analysis in another language (no model re-run)."""
    session_id: str
    language: str = "en"
    force: bool = False


class AssistantRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=600)
    context: dict[str, Any] = Field(default_factory=dict,
                                    description="Everything the analysis already computed")
    language: Lang = "en"
    allow_llm: bool = True


class AssistantResponse(BaseModel):
    answer: str
    intent: str
    language: str
    grounded: bool
    engine: str
    sources: list[str]
    disclaimer: str


class SensorIngestRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    soil_moisture_pct: float = Field(..., ge=0, le=100)
    temperature_c: float = Field(..., ge=-20, le=70)
    humidity_pct: float | None = Field(None, ge=0, le=100)
    soil_ph: float | None = Field(None, ge=0, le=14)
    battery_pct: float | None = Field(None, ge=0, le=100)
    rssi_dbm: int | None = None
    ts: str | None = None
    language: Lang = "en"


class AnalysisResponse(BaseModel):
    """One analysis = prediction + risk + irrigation + weather + index + actions."""

    session_id: str
    language: str
    generated_at: str
    prediction: dict[str, Any] | None
    risk: dict[str, Any] | None
    irrigation: dict[str, Any] | None
    weather: dict[str, Any] | None
    sustainability: dict[str, Any] | None
    actions: list[dict[str, Any]] = []
    recommendations: dict[str, Any] | None = None
    crop_recommendation: dict[str, Any] | None = None
    sensors: dict[str, Any] | None = None
    narrative: str = ""
    warnings: list[str] = []
    disclaimer: str = ""


class HealthResponse(BaseModel):
    status: str
    version: str
    build_id: str = "dev"      # stamped by `npm run build`; used to spot a stale UI
    model_available: bool
    model: dict[str, Any]
    uptime_s: float
    demo_mode: bool = False
    # Undeclared fields are silently dropped by response_model - keep this here.
    uploads: dict[str, Any] = {}
    assistant: dict[str, Any] = {}
