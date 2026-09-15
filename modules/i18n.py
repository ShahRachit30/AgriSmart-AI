"""Tiny dependency-free i18n layer (English / Hindi / Gujarati).

Every user-facing string in the API responses and the frontend goes through
`t(key, lang)`. Missing translations fall back to English and are *reported*
by `missing_keys()` so a test can assert full coverage of the three languages.

Add a language: add a column to `STRINGS` + the tag to `LANGS`.
"""
from __future__ import annotations

LANGS = ("en", "hi", "gu")
DEFAULT_LANG = "en"

STRINGS: dict[str, dict[str, str]] = {
    "app_name": {"en": "AgriSmart AI", "hi": "एग्रीस्मार्ट AI", "gu": "એગ્રીસ્માર્ટ AI"},
    "tagline": {
        "en": "Intelligent agriculture for a sustainable future",
        "hi": "सतत कृषि के लिए बुद्धिमान तकनीक",
        "gu": "ટકાઉ ખેતી માટે બુદ્ધિશાળી તકનીક",
    },
    "risk_low": {"en": "Low", "hi": "कम", "gu": "નીચું"},
    "risk_moderate": {"en": "Moderate", "hi": "मध्यम", "gu": "મધ્યમ"},
    "risk_high": {"en": "High", "hi": "उच्च", "gu": "ઊંચું"},
    "risk_critical": {"en": "Critical", "hi": "गंभीर", "gu": "ગંભીર"},
    "healthy": {"en": "Healthy", "hi": "स्वस्थ", "gu": "સ્વસ્થ"},
    "irrigate_now": {"en": "Irrigate now", "hi": "अभी सिंचाई करें", "gu": "હમણાં સિંચાઈ કરો"},
    "delay_irrigation": {
        "en": "Delay irrigation", "hi": "सिंचाई टालें", "gu": "સિંચાઈ મુલતવી રાખો",
    },
    "monitor": {"en": "Monitor", "hi": "निगरानी रखें", "gu": "નજર રાખો"},
    "no_action": {"en": "No action needed", "hi": "कोई कार्रवाई ज़रूरी नहीं", "gu": "કોઈ કાર્યવાહી જરૂરી નથી"},
    "confidence_low": {
        "en": "Low confidence - please re-photograph the leaf",
        "hi": "कम भरोसा - कृपया पत्ती की नई फोटो लें",
        "gu": "ઓછો ભરોસો - કૃપા કરીને પાનનો નવો ફોટો લો",
    },
    "weather_offline": {
        "en": "Live weather unavailable - using the values you entered.",
        "hi": "लाइव मौसम उपलब्ध नहीं - आपके दर्ज मानों का उपयोग किया गया।",
        "gu": "લાઇવ હવામાન ઉપલબ્ધ નથી - તમે દાખલ કરેલા મૂલ્યો વપરાયા.",
    },
    "upload_invalid": {
        "en": "Please upload a valid crop image.",
        "hi": "कृपया एक वैध फसल छवि अपलोड करें।",
        "gu": "કૃપા કરીને માન્ય પાકની છબી અપલોડ કરો.",
    },
    "model_unavailable": {
        "en": "Disease model is not loaded yet. Train it with model/train.py.",
        "hi": "रोग मॉडल अभी लोड नहीं है। इसे model/train.py से प्रशिक्षित करें।",
        "gu": "રોગ મોડેલ હજી લોડ નથી. તેને model/train.py થી તાલીમ આપો.",
    },
    "samples_note": {
        "en": "Real PlantDoc field photos (MIT licence). 'right' samples are classified "
              "correctly and show a clean path through the app; 'hard' samples are the model's "
              "confident mistakes and honestly show the verify path.",
        "hi": "असली PlantDoc खेत की फोटो (MIT लाइसेंस)। 'right' नमूने सही पहचाने जाते हैं और ऐप का "
              "साफ़ रास्ता दिखाते हैं; 'hard' नमूने मॉडल की भरोसेमंद ग़लतियाँ हैं और ईमानदारी से "
              "पुष्टि का रास्ता दिखाते हैं।",
        "gu": "સાચા PlantDoc ખેતરના ફોટા (MIT લાઇસન્સ). 'right' નમૂના સાચા ઓળખાય છે અને એપનો "
              "સ્પષ્ટ માર્ગ બતાવે છે; 'hard' નમૂના મોડેલની ભરોસાપાત્ર ભૂલો છે અને પ્રામાણિકપણે "
              "ખાતરી કરવાનો માર્ગ બતાવે છે.",
    },
    "devices_note": {
        "en": "No physical ESP32 is attached in this deployment; these are simulated nodes that "
              "publish the documented firmware JSON every 5 minutes.",
        "hi": "इस डिप्लॉयमेंट में कोई असली ESP32 नहीं जुड़ा है; ये सिम्युलेटेड नोड हैं जो हर 5 मिनट "
              "में तय फ़र्मवेयर JSON भेजते हैं।",
        "gu": "આ ડિપ્લોયમેન્ટમાં કોઈ સાચું ESP32 જોડાયું નથી; આ સિમ્યુલેટેડ નોડ છે જે દર 5 મિનિટે "
              "નક્કી કરેલ ફર્મવેર JSON મોકલે છે.",
    },
    "crop_rec_skipped": {
        "en": "Crop recommendation skipped",
        "hi": "फसल-सुझाव छोड़ा गया",
        "gu": "પાક-સૂચન છોડ્યું",
    },
    "not_a_leaf": {
        "en": "This photo does not look like a leaf. I stopped before diagnosing anything - a "
              "confident answer about the wrong subject is worse than no answer.",
        "hi": "यह फोटो पत्ती की नहीं लगती। मैंने निदान से पहले ही रुक गया - गलत विषय पर भरोसेमंद उत्तर "
              "न मिलने से भी बुरा है।",
        "gu": "આ ફોટો પાન જેવો લાગતો નથી. મેં નિદાન પહેલાં જ અટકી ગયો - ખોટા વિષય પર ભરોસાપાત્ર જવાબ "
              "ન મળવા કરતાં પણ ખરાબ છે.",
    },
    "not_a_leaf_hint": {
        "en": "Fill the frame with a single leaf in daylight, then upload again - or tap one of the "
              "verified sample photos on the dashboard to see a full analysis.",
        "hi": "दिन की रोशनी में एक ही पत्ती फ्रेम में भरें, फिर दोबारा अपलोड करें - या डैशबोर्ड पर दिए "
              "प्रमाणित नमूना फोटो में से कोई चुनें।",
        "gu": "દિવસના અજવાળામાં એક જ પાન ફ્રેમમાં ભરો, પછી ફરી અપલોડ કરો - અથવા ડેશબોર્ડ પરના "
              "ચકાસાયેલા નમૂના ફોટામાંથી એક પસંદ કરો.",
    },
    "leaf_uncertain": {
        "en": "This does not look like a clear, close-up leaf photo - the diagnosis below may be "
              "unreliable. Please retake it if you can.",
        "hi": "यह साफ़, नज़दीक से ली गई पत्ती की फोटो नहीं लगती - नीचे का निदान अविश्वसनीय हो सकता है। "
              "संभव हो तो नई फोटो लें।",
        "gu": "આ સ્પષ્ટ, નજીકથી લીધેલો પાનનો ફોટો લાગતો નથી - નીચેનું નિદાન અવિશ્વસનીય હોઈ શકે છે. "
              "શક્ય હોય તો નવો ફોટો લો.",
    },
    "leaf_checked": {
        "en": "Checked: this looks like a leaf photo ({p} % leaf confidence).",
        "hi": "जाँचा गया: यह पत्ती की फोटो लगती है ({p}% भरोसा)।",
        "gu": "તપાસ્યું: આ પાનનો ફોટો લાગે છે ({p}% ભરોસો).",
    },
    "disclaimer": {
        "en": "Advisory only - confirm with your local agriculture officer before chemical use.",
        "hi": "केवल सलाह - रसायन के उपयोग से पहले स्थानीय कृषि अधिकारी से पुष्टि करें।",
        "gu": "ફક્ત સલાહ - રસાયણ વાપરતા પહેલાં સ્થાનિક કૃષિ અધિકારી સાથે ખાતરી કરો.",
    },
}


def normalise(lang: str | None) -> str:
    """Map 'hi-IN' | 'HI' | None -> 'hi' (falls back to DEFAULT_LANG)."""
    if not lang:
        return DEFAULT_LANG
    tag = str(lang).strip().lower().replace("_", "-").split("-")[0]
    return tag if tag in LANGS else DEFAULT_LANG


def t(key: str, lang: str | None = None, **fmt) -> str:
    """Translate `key`; unknown keys return the key itself (never raises)."""
    lang = normalise(lang)
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry[DEFAULT_LANG]
    try:
        return text.format(**fmt) if fmt else text
    except (KeyError, IndexError):
        return text


def to_en(text: str | None) -> str | None:
    """Reverse lookup: 'गंभीर' / 'ગંભીર' -> 'Critical'.

    Context objects are built in *one* language (the analysis language) and may be
    replayed by a question in another - a user analyses in Gujarati, switches the
    language selector, then asks in English. Without this, the old language leaks
    into the new answer ("at મધ્યમ risk level").
    """
    if not text:
        return text
    out = str(text)
    for row in STRINGS.values():
        en = row.get("en")
        if not en:
            continue
        for lang in LANGS:
            local = row.get(lang)
            if lang != "en" and local and local != en and local in out:
                out = out.replace(local, en)
    return out


def missing_keys(lang: str) -> list[str]:
    """Keys without an explicit translation for `lang` (empty == fully localised)."""
    lang = normalise(lang)
    return sorted(k for k, v in STRINGS.items() if not v.get(lang))


def supported() -> tuple[str, ...]:
    return LANGS
