"""Bonus E - Farmer Assistant: grounded, provenance-carrying Q&A.

Design contract
---------------
1. **No invented facts.** Every number in an answer is copied from the
   `context` object the caller passes (prediction, weather, irrigation,
   sustainability, crop recommendation). If a value is missing the assistant
   says so instead of guessing.
2. **Deterministic.** `answer_grounded()` is a pure function of
   (question, context, lang) - so it is unit-testable and offline-safe.
3. **Traceable.** The response carries `sources[]` naming exactly which context
   keys were used, plus `intent` and `grounded: true`.
4. **Optional LLM.** If ``GROQ_API_KEY`` (preferred, fast + free tier),
   ``OPENAI_API_KEY`` or ``GEMINI_API_KEY`` is set,
   `answer()` asks the LLM *with the same context embedded* and a no-invention
   system prompt; on any error it silently returns the grounded answer.
   Without keys (the judged default) the grounded engine answers.

`STRICT_GROUNDING_NOTE` is what the LLM is told; it is also surfaced in the UI.
"""
from __future__ import annotations

import json
import os
import re

from .env import load_env

load_env()          # `.env` next to run.sh; real environment variables win
from typing import Any

from .i18n import normalise, t, to_en
from . import assistant_i18n as asi18n

STRICT_GROUNDING_NOTE = (
    "You are AgriSmart AI's assistant for smallholder farmers. Answer ONLY with facts that "
    "appear in the supplied CONTEXT JSON. Never invent pesticide names, doses, prices or weather "
    "numbers that are not in the context. If the context lacks the answer, say so plainly and "
    "suggest the next concrete step. Prefer organic/low-cost actions first. Reply in the "
    "requested language, in at most 120 words, plain sentences."
)

# Ordered most-specific -> most-generic: the first intent whose keyword count is
# maximal wins, so "how much will the medicine cost?" routes to `cost`, not to the
# generic `treatment` bucket. Keep this dict in priority order.
#
# Every intent carries keywords in English, Devanagari (hi) and Gujarati script,
# plus romanised Hinglish/Gujlish - a farmer typing "mere tamatar ke patte par
# daag hai" on a phone keyboard must land in the same bucket as the English.
INTENTS: dict[str, tuple[str, ...]] = {
    "greeting": ("hello", "hi ", "namaste", "नमस्ते", "નમસ્તે", "kem cho", "kem chho"),
    "cost": ("cost", "price", "expensive", "cheap", "खर्च", "कीमत", "ખર્ચ", "કિંમત",
             "kharch", "kimat", "keemat", "bhav", "ka rate", "kitne ka", "paisa", "kitna paisa"),
    "organic": ("organic", "neem", "natural", "without chemical", "जैविक", "नीम", "જૈવિક",
                "લીમડો", "jaivik", "limdo"),
    "irrigation": ("irrigat", "moisture", "how much water", "water the", "watering",
                   "सिंचाई", "पानी", "પાણી", "સિંચાઈ",
                   "sinchai", "sehchai", "pani", "paani", "pani kab", "paani kab"),
    "weather": ("weather", "rain", "temperature", "humidity", "forecast",
                "मौसम", "बारिश", "बरसात", "હવામાન", "વરસાદ", "mausam", "barish", "varsad"),
    "sustainability": ("sustainab", "score", "index", "eco-friendly", "green",
                       "टिकाऊ", "સસ્ટેન", "ટકાઉ", "takau"),
    # The disease family sits *above* the generic `crop` bucket on purpose: a tie
    # means both matched once, and "મારા પાકમાં રોગ છે" (my crop has a disease) is a
    # question about the disease, not about which crop to plant. Ties are resolved
    # by this order, so cost stays above treatment ("medicine cost" -> cost) and
    # organic stays above treatment ("neem instead of spray" -> organic).
    "prevention": ("prevent", "avoid", "stop", "रोकथाम", "बचाव", "અટકાવ", "roktham", "bachav"),
    "treatment": ("treat", "cure", "spray", "pesticide", "fungicide", "medicine", "dose",
                  "कीटनाश", "दवा", "फफूंद", "छिड़क", "इलाज", "દવા", "છંટકાવ", "જંતુનાશક",
                  "ઉપાય", "ઇલાજ", "ઉપચાર", "ilaj", "dawa", "davai", "upchar"),
    "disease": ("disease", "spot", "blight", "rust", "mold", "mould", "rot", "scab", "infection",
                "बीमारी", "रोग", "छाल", "धब्ब", "રોગ", "છાલ", "ચાંઠું", "ડાઘ", "ધબ્બા",
                "સુકારો", "bimari", "rog", "daag", "dhabba", "sukaro"),
    "crop": ("which crop", "recommend", "suggest crop", "kharif", "rabi",
             "फसल", "પાક", "ફસલ", "fasal"),
}

# Disease-risk words -> existing i18n label keys (Low / Moderate / High / Critical).
RISK_LABEL_KEYS = {"low": "risk_low", "moderate": "risk_moderate",
                   "high": "risk_high", "critical": "risk_critical"}

DISCLAIMER_KEYS = ("disclaimer",)


def detect_intent(question: str) -> str:
    q = (question or "").lower()
    best, best_hits = "general", 0
    for intent, keys in INTENTS.items():
        hits = sum(1 for k in keys if k in q)
        if hits > best_hits:
            best, best_hits = intent, hits
    return best


def _has(ctx: dict[str, Any], *path: str) -> Any:
    cur: Any = ctx
    for p in path:
        if not isinstance(cur, dict) or p not in cur or cur[p] is None:
            return None
        cur = cur[p]
    return cur


def _sources_used(ctx: dict[str, Any], wanted: list[str]) -> list[str]:
    label = {
        "prediction": "crop-disease model output",
        "prediction.slug": "crop-disease model output",
        "risk": "AgriSmart knowledge base (KB v1)",
        "irrigation": "irrigation rule engine (modules/weather.py)",
        "weather": "Open-Meteo live weather (or manual input when offline)",
        "sustainability": "AgriSmart Sustainability Index formula",
        "crop_recommendation": "RandomForest crop-recommendation model (Bonus A)",
        "sensors": "simulated IoT sensor feed (modules/iot_sim.py)",
    }
    out = []
    for w in wanted:
        if _has(ctx, *w.split(".")) is not None:
            out.append(label.get(w, w))
    return out


def _fmt_pct(v: Any) -> str:
    try:
        return f"{float(v) * 100:.0f}%"
    except (TypeError, ValueError):
        return "n/a"


def _risk_word(risk_word: Any, lang: str) -> str:
    """Localize 'Critical' -> 'गंभीर', and un-localise a context built in another
    language first (a session can switch language between Analyze and a question)."""
    if not risk_word:
        return asi18n.say("risk_unreported", lang)
    canon = str(to_en(str(risk_word))).strip()
    key = RISK_LABEL_KEYS.get(canon.lower())
    return t(key, lang) if key else canon


def answer_grounded(question: str, context: dict[str, Any] | None = None,
                    lang: str | None = None) -> dict[str, Any]:
    """Deterministic, context-bound answer, rendered in the requested language.

    Structure is identical in all three languages; only the sentence templates
    differ (modules/assistant_i18n.py). Knowledge-base lines - product names,
    doses, agronomy bullets - are quoted verbatim in English and introduced by a
    localized "quoted from the knowledge base, in English" label, because a
    machine-translated pesticide dose would be worse than leaving it alone.
    """
    ctx = context or {}
    lang = normalise(lang)
    say = lambda key, **fmt: asi18n.say(key, lang, **fmt)  # noqa: E731
    intent = detect_intent(question)
    pred = _has(ctx, "prediction") or {}
    risk = _has(ctx, "risk") or {}
    irr = _has(ctx, "irrigation") or {}
    wx = _has(ctx, "weather") or {}
    sus = _has(ctx, "sustainability") or {}
    rec = _has(ctx, "crop_recommendation") or {}
    sensors = _has(ctx, "sensors") or {}

    slug = pred.get("class") or pred.get("slug")
    crop = risk.get("crop") or pred.get("crop")
    condition = risk.get("condition") or pred.get("condition") or slug
    conf = pred.get("confidence")
    risk_word = risk.get("risk_label") or risk.get("risk")

    # Localized nouns: the KB names stay English, the sentence around them does not.
    cond_disp = asi18n.localize_condition(condition, lang) if condition else None
    crop_disp = asi18n.localize_crop(crop, lang) if crop else None
    conf_disp = _fmt_pct(conf) if conf is not None else None

    parts: list[str] = []
    used: list[str] = []

    if intent == "greeting" or not question.strip():
        parts.append(say("greeting"))
        used = ["prediction"]

    elif intent in ("disease", "treatment", "organic", "prevention", "cost"):
        if condition:
            line = say("reads", cond=cond_disp)
            if crop_disp:
                line += say("on_crop", crop=crop_disp)
            if conf_disp is not None:
                line += say("confidence", conf=conf_disp)
            line += say("risk_level", risk=_risk_word(risk_word, lang))
            parts.append(line)
            used += ["prediction", "prediction.slug", "risk"]
        else:
            parts.append(say("no_prediction"))
        if intent in ("organic", "treatment", "prevention"):
            organic = risk.get("organic_actions") or []
            chem = risk.get("chemical_option")
            prev = risk.get("prevention") or []
            if organic:
                parts.append(say("organic_actions",
                                 list=" ".join(f"({i + 1}) {a}" for i, a in enumerate(organic[:3]))))
            if intent == "organic" and not chem:
                parts.append(say("no_chemical"))
            if intent == "treatment" and chem:
                parts.append(say("chemical_escalation", product=chem.get("product"),
                                 dose=chem.get("dose"), note=chem.get("note", "")))
            elif intent == "treatment" and risk:
                parts.append(say("no_chemical_step"))
            if prev:
                parts.append(say("prevention_lead", list=" ".join(prev[:2])))
            used.append("risk")
        if intent == "cost":
            parts.append(say("cost_caveat"))
        if intent == "prevention" and not risk.get("prevention"):
            parts.append(say("prevention_needs_detection"))

    elif intent == "irrigation":
        if irr:
            parts.append(say("irrigation_decision",
                             action=irr.get("action_label") or irr.get("action")))
            reasons = [r.rstrip(". ") for r in (irr.get("reasons") or [])[:2]]
            if reasons:
                parts.append(say("irrigation_reason", reason="; ".join(reasons) + "."))
            if irr.get("soil_moisture_pct") is not None:
                parts.append(say("soil_moisture_line", m=f"{irr['soil_moisture_pct']:.0f}"))
            used.append("irrigation")
        else:
            parts.append(say("no_irrigation"))
        if sensors:
            parts.append(say("sensors_line", m=sensors.get("soil_moisture_pct"),
                             t=sensors.get("temperature_c")))
            used.append("sensors")

    elif intent == "weather":
        if wx and wx.get("ok"):
            parts.append(say("weather_live", city=wx.get("city") or say("weather_here"),
                             cond=wx.get("condition"), t=wx.get("temperature_c"),
                             h=wx.get("humidity_pct"), w=wx.get("wind_kph"),
                             p=wx.get("rain_probability_pct"), mm=wx.get("weekly_rain_mm")))
            used.append("weather")
        elif wx:
            parts.append(t("weather_offline", lang) + " " + say("weather_offline_extra"))
        else:
            parts.append(say("no_weather"))

    elif intent == "sustainability":
        if sus:
            parts.append(say("sus_index", total=sus.get("total"), grade=sus.get("grade"),
                             band=asi18n.localize_band(sus.get("band"), lang),
                             formula=sus.get("formula")))
            subs = sus.get("subscores") or {}
            if subs:
                parts.append(say("sus_subscores", list=", ".join(
                    f"{asi18n.localize_subscore(k, lang)} {v}" for k, v in subs.items())))
            if sus.get("weakest_area"):
                weak = sus["weakest_area"]
                first = (sus.get("reasons", {}) or {}).get(weak, [])
                parts.append(say("sus_weakest", area=asi18n.localize_subscore(weak, lang),
                                 reason=": " + first[0] if first else "",
                                 tip=sus.get("top_tip")))
            used.append("sustainability")
        else:
            parts.append(say("no_sus"))

    elif intent == "crop":
        if rec and rec.get("recommendations"):
            top = rec["recommendations"][:3]
            parts.append(say("crop_rank",
                             list=", ".join(f"{asi18n.localize_crop(r.get('crop'), lang)} "
                                            f"({_fmt_pct(r.get('probability'))})" for r in top)))
            used.append("crop_recommendation")
        else:
            parts.append(say("no_crop"))

    else:
        bits = cond_disp or say("general_bits_none")
        if risk_word:
            bits += say("general_bits_risk", risk=_risk_word(risk_word, lang))
        if irr.get("action_label"):
            bits += say("general_bits_irrigation", action=irr["action_label"])
        if sus.get("total") is not None:
            bits += say("general_bits_sus", total=sus["total"])
        parts.append(say("general_intro", bits=bits))
        used += ["prediction", "risk", "irrigation", "sustainability"]
        parts.append(say("general_hint"))

    used.append("disclaimer")
    return {
        "answer": " ".join(p for p in parts if p).strip(),
        "intent": intent,
        "language": lang,
        "grounded": True,
        "engine": "grounded-rules",
        "sources": [asi18n.localize_source(s, lang)
                    for s in _sources_used(ctx, list(dict.fromkeys(used)))],
        "disclaimer": t("disclaimer", lang),
    }


# Written out for the model: "answer in 'gu'" is ambiguous to smaller models, so the
# instruction names the language and its script explicitly.
LANG_INSTRUCTION = {
    "en": "Answer in English.",
    "hi": "Answer in Hindi, written in Devanagari script (हिन्दी).",
    "gu": "Answer in Gujarati, written in Gujarati script (ગુજરાતી).",
}


def _llm_prompt(question: str, ctx: dict[str, Any], lang: str) -> str:
    return (f"CONTEXT JSON:\n{json.dumps(ctx, ensure_ascii=False, default=str)[:6000]}\n\n"
            f"QUESTION ({lang}): {question}\n"
            f"{LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION['en'])} "
            f"Keep numbers, product names and doses exactly as they appear in the context. "
            f"Reply in 2-4 short sentences.")


def _try_openai(question: str, ctx: dict[str, Any], lang: str, timeout: float = 20.0) -> str | None:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    text, _ = _try_openai_compatible(os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                                     key, os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                                     question, ctx, lang, timeout)
    return text


# Groq speaks the OpenAI chat-completions dialect, so both providers share one
# implementation - only the base URL, the key and the model name differ.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# NOTE: Groq retires models (llama-3.3-70b-versatile was retired in 2026), so the
# default is a *list*: if the first choice answers "model_not_found" the next one is
# tried, and `GET /api/health` reports which model actually served the answer.
GROQ_MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b")
GROQ_DEFAULT_MODEL = GROQ_MODELS[0]
_THINK_RE = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.S | re.I)


def _clean_completion(text: str) -> str:
    """Drop reasoning traces some models emit (qwen3 opens with <think>…</think>)."""
    return _THINK_RE.sub("", text or "").strip()


def _max_tokens() -> int:
    """Output budget. Generous by default: gpt-oss-style models spend part of it on
    hidden reasoning, and a small cap truncates the visible answer mid-word."""
    try:
        return max(120, int(os.getenv("GROQ_MAX_TOKENS", "900")))
    except ValueError:
        return 900


def _try_openai_compatible(base_url: str, api_key: str, models: tuple[str, ...] | list[str],
                           question: str, ctx: dict[str, Any], lang: str,
                           timeout: float) -> tuple[str | None, str | None]:
    """POST to any OpenAI-compatible /chat/completions endpoint (Groq, OpenAI, proxies).

    Accepts a *list* of models and moves to the next one when the API says the model
    does not exist (Groq retires models regularly). Returns `(text, model_used)`.
    """
    if isinstance(models, str):
        models = [models]
    import time as _time
    import requests
    payload_messages = [{"role": "system", "content": STRICT_GROUNDING_NOTE},
                        {"role": "user", "content": _llm_prompt(question, ctx, lang)}]
    for model in models:
        for attempt in (0, 1):                     # one retry, only for a rate limit
            try:
                r = requests.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}",
                             "Content-Type": "application/json"},
                    json={"model": model, "temperature": 0.2, "max_tokens": _max_tokens(),
                          "messages": payload_messages},
                    timeout=timeout,
                )
                if r.status_code == 429 and attempt == 0:
                    # free tiers throttle bursts (a farmer tapping several chips).
                    # Wait a moment and retry the same model once before giving up.
                    _LAST_ERROR["llm"] = "rate_limited (429) - retried"
                    _time.sleep(0.9)
                    continue
                if r.status_code in (400, 404) and attempt == 0:
                    body = (r.text or "").lower()
                    if "model" in body and any(k in body for k in
                                               ("not exist", "not_found", "not found", "no access")):
                        _LAST_ERROR["llm"] = f"model unavailable: {model}"
                        break                      # next model
                r.raise_for_status()
                body_json = r.json()
                choice = (body_json.get("choices") or [{}])[0]
                text = _clean_completion(choice.get("message", {}).get("content"))
                if text:
                    _LAST_ERROR.pop("llm", None)   # a success clears the recorded reason
                    if choice.get("finish_reason") == "length":
                        # usable, but the model ran out of budget - worth surfacing
                        _LAST_ERROR["llm"] = "answer truncated (finish_reason=length)"
                    return text, model
                _LAST_ERROR["llm"] = "empty completion"
                break
            except Exception as exc:               # noqa: BLE001 - never break the chat
                _LAST_ERROR["llm"] = f"{type(exc).__name__}: {str(exc)[:80]}"
                break
    return None, None


def _try_groq(question: str, ctx: dict[str, Any], lang: str, timeout: float = 20.0) -> str | None:
    """Groq (LPU inference): fast, free tier, OpenAI-compatible, EN/HI/GU capable."""
    key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not key:
        return None
    configured = (os.getenv("GROQ_MODEL") or "").strip()
    models = [configured] if configured else []
    models += [m for m in GROQ_MODELS if m != configured]      # fall back on retirement
    text, used = _try_openai_compatible(os.getenv("GROQ_BASE_URL", GROQ_BASE_URL), key,
                                        models, question, ctx, lang, timeout)
    if used:
        _SERVED_MODEL["groq"] = used
    return text


def _try_gemini(question: str, ctx: dict[str, Any], lang: str, timeout: float = 20.0) -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    import requests
    try:
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key},
            json={"system_instruction": {"parts": [{"text": STRICT_GROUNDING_NOTE}]},
                  "contents": [{"parts": [{"text": _llm_prompt(question, ctx, lang)}]}],
                  "generationConfig": {"temperature": 0.2, "maxOutputTokens": 350}},
            timeout=timeout,
        )
        r.raise_for_status()
        cands = r.json().get("candidates") or []
        text = "".join(p.get("text", "") for p in (cands[0]["content"]["parts"] if cands else [])).strip()
        return text or None
    except Exception:
        return None


PROVIDERS = ("groq", "openai", "gemini")


def active_provider() -> str | None:
    """Which LLM provider will be used, in priority order (Groq first).

    `AGRISMART_DISABLE_LLM=1` forces the deterministic engine even when keys exist
    (useful for offline judging, debugging, or a reproducible demo).
    """
    if (os.getenv("AGRISMART_DISABLE_LLM") or "").strip() not in ("", "0", "false", "False"):
        return None
    if (os.getenv("GROQ_API_KEY") or "").strip():
        return "groq"
    if (os.getenv("OPENAI_API_KEY") or "").strip():
        return "openai"
    if (os.getenv("GEMINI_API_KEY") or "").strip():
        return "gemini"
    return None


_SERVED_MODEL: dict[str, str] = {}      # provider -> model that last answered successfully
_LAST_ERROR: dict[str, str] = {}        # provider/llm -> why it last failed (for /api/health)


def served_model(provider: str | None = None) -> str | None:
    """The model that actually produced the last answer (may differ from the configured one)."""
    return _SERVED_MODEL.get(provider or active_provider() or "", None)


def provider_model(provider: str | None = None) -> str | None:
    provider = provider or active_provider()
    return {"groq": lambda: os.getenv("GROQ_MODEL", GROQ_DEFAULT_MODEL),
            "openai": lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "gemini": lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash")}.get(
                provider, lambda: None)()


def llm_status() -> dict[str, Any]:
    """What the health/meta endpoints publish: never the key itself."""
    provider = active_provider()
    return {
        "llm_enabled": provider is not None,
        "provider": provider,
        "model": provider_model(provider),
        "model_used": served_model(provider),          # filled in after the first answer
        "mode": ("grounded rules (no key set)" if provider is None
                 else "grounded context + LLM"),
        "keys_seen": [p for p in PROVIDERS
                      if (os.getenv(f"{p.upper()}_API_KEY") or "").strip()],
        # why the LLM was skipped, when it was (never contains the key)
        "last_error": _LAST_ERROR.get("llm"),
    }


def answer(question: str, context: dict[str, Any] | None = None, lang: str | None = None,
           allow_llm: bool = True) -> dict[str, Any]:
    """Public entry point: LLM when a key exists and `allow_llm`, else grounded rules.

    The grounded answer is always computed first - it is the fallback *and* the
    source of everything the LLM is allowed to talk about (the context is built
    from it), so a provider outage can never produce an invented answer.
    """
    grounded = answer_grounded(question, context, lang)
    if not allow_llm:
        return grounded
    provider = active_provider()
    if provider is None:
        return grounded
    ctx = context or {}
    lg = grounded["language"]
    order = [provider] + [p for p in PROVIDERS if p != provider]   # preferred first, then fallbacks
    for name in order:
        text = {"groq": _try_groq, "openai": _try_openai, "gemini": _try_gemini}[name](question, ctx, lg)
        if text:
            return {**grounded, "answer": text, "engine": f"llm+grounded-context ({name})",
                    "provider": name, "model_used": served_model(name), "grounded": True,
                    "llm_note": "Answer generated from the supplied context only."}
    grounded["engine"] = "grounded-rules (LLM unavailable)"
    grounded["provider"] = provider
    return grounded


# Kept for backwards compatibility with the earlier code and the tests: computed
# lazily now, so a `.env` written after import is honoured.
def __getattr__(name: str):          # pragma: no cover - module attribute shim
    if name == "LLM_ENABLED":
        return active_provider() is not None
    raise AttributeError(name)
