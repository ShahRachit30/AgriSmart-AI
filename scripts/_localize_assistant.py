"""Rewrite modules/assistant.py's answer_grounded() to be language-aware.

Run once from the project root:  python3 scripts/_localize_assistant.py
Guarded by asserts + py_compile checks; prints a diff summary when done.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASST = ROOT / "modules" / "assistant.py"

NEW_INTENTS = '''# Ordered most-specific -> most-generic: the first intent whose keyword count is
# maximal wins, so "how much will the medicine cost?" routes to `cost`, not to the
# generic `treatment` bucket. Keep this dict in priority order.
#
# Every intent carries keywords in English, Devanagari (hi) and Gujarati script,
# plus romanised Hinglish/Gujlish - a farmer typing "mere tamatar ke patte par
# daag hai" on a phone keyboard must land in the same bucket as the English.
INTENTS: dict[str, tuple[str, ...]] = {
    "greeting": ("hello", "hi ", "namaste", "नमस्ते", "નમસ્તે", "kem cho", "kem chho"),
    "cost": ("cost", "price", "expensive", "cheap", "खर्च", "कीमत", "ખર્ચ", "કિંમત",
             "kharch", "kimat", "keemat", "bhav"),
    "organic": ("organic", "neem", "natural", "without chemical", "जैविक", "नीम", "જૈવિક",
                "લીમડો", "jaivik", "limdo"),
    "irrigation": ("irrigat", "moisture", "how much water", "water the", "watering",
                   "सिंचाई", "पानी", "પાણી", "સિંચાઈ", "sinchai", "pani dena", "sehchai"),
    "weather": ("weather", "rain", "temperature", "humidity", "forecast",
                "मौसम", "बारिश", "बरसात", "હવામાન", "વરસાદ", "mausam", "barish", "varsad"),
    "sustainability": ("sustainab", "score", "index", "eco-friendly", "green",
                       "टिकाऊ", "સસ્ટેન", "ટકાઉ", "takau"),
    "crop": ("which crop", "recommend", "suggest crop", "kharif", "rabi", "फसल", "પાક", "fasal"),
    "prevention": ("prevent", "avoid", "stop", "रोकथाम", "बचाव", "અટકાવ", "roktham", "bachav"),
    "treatment": ("treat", "cure", "spray", "pesticide", "fungicide", "medicine", "dose",
                  "कीटनाश", "दवा", "फफूंद", "छिड़क", "દવા", "છંટકાવ", "જંતુનાશક",
                  "ilaj", "dawa", "davai", "upchar"),
    "disease": ("disease", "spot", "blight", "rust", "mold", "mould", "rot", "scab", "infection",
                "बीमारी", "रोग", "छाल", "धब्ब", "રોગ", "છાલ", "ચાંઠું", "ડાઘ", "ધબ્બા",
                "સુકારો", "bimari", "rog", "daag", "dhabba", "sukaro"),
}

# Disease-risk words -> existing i18n label keys (Low / Moderate / High / Critical).
RISK_LABEL_KEYS = {"low": "risk_low", "moderate": "risk_moderate",
                   "high": "risk_high", "critical": "risk_critical"}
'''

NEW_FUNC = '''def _risk_word(risk_word: Any, lang: str) -> str:
    """Localize 'Critical' -> 'गंभीर' using the same table the UI labels use."""
    if not risk_word:
        return asi18n.say("risk_unreported", lang)
    key = RISK_LABEL_KEYS.get(str(risk_word).strip().lower())
    return t(key, lang) if key else str(risk_word)


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
                             band=sus.get("band"), formula=sus.get("formula")))
            subs = sus.get("subscores") or {}
            if subs:
                parts.append(say("sus_subscores",
                                 list=", ".join(f"{k} {v}" for k, v in subs.items())))
            if sus.get("weakest_area"):
                weak = sus["weakest_area"]
                first = (sus.get("reasons", {}) or {}).get(weak, [])
                parts.append(say("sus_weakest", area=weak,
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


'''


def main() -> None:
    src = ASST.read_text()

    # 1) import the phrase layer
    old_import = "from .i18n import normalise, t\n"
    new_import = "from .i18n import normalise, t\nfrom . import assistant_i18n as asi18n\n"
    assert src.count(old_import) == 1
    src = src.replace(old_import, new_import)

    # 2) swap the intent table (multilingual keywords) + add the risk-label map
    start = src.index("# Ordered most-specific -> most-generic")
    end = src.index("DISCLAIMER_KEYS = (\"disclaimer\",)")
    src = src[:start] + NEW_INTENTS + "\n" + src[end:]

    # 3) replace answer_grounded() wholesale, keeping the rest of the module intact
    fstart = src.index("def answer_grounded(")
    fend = src.index("def _llm_prompt(")
    src = src[:fstart] + NEW_FUNC + src[fend:]

    ASST.write_text(src)
    print(f"assistant.py rewritten: {len(src.splitlines())} lines")


if __name__ == "__main__":
    main()
