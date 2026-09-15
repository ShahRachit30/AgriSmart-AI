"""Sentence-level localisation for the Bonus-E assistant (en / hi / gu).

Why this file exists
--------------------
`modules/i18n.py` handles *labels* ("Low", "Irrigate now"), which is enough for the
UI chrome but not for a multi-sentence advisory. A farmer who asks in Gujarati must
get an answer in Gujarati, not an English paragraph under a translated button - so
the assistant's sentence templates live here, one row per sentence, three columns.

Honesty rule
------------
The knowledge base (`modules/recommendations.py`) is written in English: product
names, doses and agronomy lines are quoted *verbatim* from it, because a machine
translation of a pesticide dose is worse than no translation at all. Those quoted
lines are introduced by a localized "quoted from the knowledge base, in English"
label, and a test asserts the label is present whenever quoted text is emitted.

Adding a language: add a column to every row here + the tag to `i18n.LANGS`.
`checks()` returns the ids that are missing a language, and the test suite fails if
that list is not empty.
"""
from __future__ import annotations

import re
from typing import Any

LANGS = ("en", "hi", "gu")

# --- sentence templates ---------------------------------------------------- #
PHRASES: dict[str, dict[str, str]] = {
    "greeting": {
        "en": "Namaste! I can explain the disease result, the irrigation decision, the weather "
              "outlook, the sustainability score or the crop suggestion - ask about any of them "
              "using the numbers already on this screen.",
        "hi": "नमस्ते! मैं रोग का नतीजा, सिंचाई का फैसला, मौसम, टिकाऊपन स्कोर या फसल का सुझाव "
              "समझा सकता हूँ - इसी स्क्रीन पर दिख रहे आँकड़ों के बारे में पूछें।",
        "gu": "નમસ્તે! હું રોગનું પરિણામ, સિંચાઈનો નિર્ણય, હવામાન, ટકાઉપણ સ્કોર કે પાકની સલાહ "
              "સમજાવી શકું છું - આ જ સ્ક્રીન પરના આંકડા વિશે પૂછો.",
    },
    "no_prediction": {
        "en": "I do not have a prediction in this session yet - take a clear photo of the affected "
              "leaf and run Analyze; then I can speak about the exact condition.",
        "hi": "इस सत्र में अभी कोई पूर्वानुमान नहीं है - प्रभावित पत्ती की साफ़ फोटो लेकर "
              "'विश्लेषण' चलाएँ; फिर मैं सटीक स्थिति बता सकता हूँ।",
        "gu": "આ સત્રમાં હજી કોઈ આગાહી નથી - અસરગ્રસ્ત પાનનો સ્પષ્ટ ફોટો લઈને 'વિશ્લેષણ' ચલાવો; "
              "પછી હું ચોક્કસ સ્થિતિ કહી શકીશ.",
    },
    "reads": {
        "en": "The analysis reads: {cond}",
        "hi": "विश्लेषण के अनुसार: {cond}",
        "gu": "વિશ્લેષણ મુજબ: {cond}",
    },
    "on_crop": {
        "en": " on {crop}",
        "hi": " - फसल: {crop}",
        "gu": " - પાક: {crop}",
    },
    "confidence": {
        "en": " (model confidence {conf})",
        "hi": " (मॉडल का भरोसा {conf})",
        "gu": " (મોડેલનો ભરોસો {conf})",
    },
    "risk_level": {
        "en": " at {risk} risk level.",
        "hi": ", जोखिम स्तर: {risk}।",
        "gu": ", જોખમ સ્તર: {risk}.",
    },
    "organic_actions": {
        "en": "Organic-first actions (quoted from the knowledge base, in English): {list}",
        "hi": "पहले जैविक उपाय (ज्ञानकोश से, अंग्रेज़ी में): {list}",
        "gu": "પ્રથમ જૈવિક ઉપાયો (જ્ઞાનકોશમાંથી, અંગ્રેજીમાં): {list}",
    },
    "no_chemical": {
        "en": "No chemical product is listed for this case.",
        "hi": "इस स्थिति के लिए कोई रासायनिक उत्पाद सूचीबद्ध नहीं है।",
        "gu": "આ સ્થિતિ માટે કોઈ રાસાયણિક ઉત્પાદન સૂચિબદ્ધ નથી.",
    },
    "chemical_escalation": {
        "en": "Chemical escalation (only if needed): {product} - {dose}. {note}",
        "hi": "रासायनिक विकल्प (सिर्फ़ ज़रूरत पड़ने पर): {product} - {dose}. {note}",
        "gu": "રાસાયણિક વિકલ્પ (ફક્ત જરૂર પડે તો): {product} - {dose}. {note}",
    },
    "no_chemical_step": {
        "en": "For this condition the knowledge base lists no chemical step - the organic and "
              "preventive actions are the whole plan.",
        "hi": "इस स्थिति के लिए ज्ञानकोश में कोई रासायनिक कदम नहीं है - जैविक और बचाव के उपाय ही "
              "पूरी योजना हैं।",
        "gu": "આ સ્થિતિ માટે જ્ઞાનકોશમાં કોઈ રાસાયણિક પગલું નથી - જૈવિક અને અટકાવના ઉપાયો જ "
              "આખી યોજના છે.",
    },
    "prevention_lead": {
        "en": "To stop it coming back: {list}",
        "hi": "दोबारा न हो, इसके लिए: {list}",
        "gu": "ફરી ન થાય તે માટે: {list}",
    },
    "cost_caveat": {
        "en": "I cannot quote prices - the knowledge base carries no market data. Your local "
              "agri-input dealer or the eNAM portal is the honest source for cost.",
        "hi": "मैं कीमत नहीं बता सकता - ज्ञानकोश में बाज़ार भाव का डेटा नहीं है। लागत के लिए अपने "
              "स्थानीय कृषि इनपुट विक्रेता या eNAM पोर्टल पर भरोसा करें।",
        "gu": "હું ભાવ કહી શકતો નથી - જ્ઞાનકોશમાં બજારભાવનો ડેટા નથી. ખર્ચ માટે તમારા સ્થાનિક "
              "કૃષિ દુકાનદાર કે eNAM પોર્ટલ વિશ્વસનીય સ્રોત છે.",
    },
    "prevention_needs_detection": {
        "en": "A prevention list appears here only after a disease is detected.",
        "hi": "रोकथाम की सूची रोग पकड़ में आने के बाद ही दिखती है।",
        "gu": "અટકાવની યાદી રોગ પકડાયા પછી જ દેખાય છે.",
    },
    "irrigation_decision": {
        "en": "Irrigation decision: {action}.",
        "hi": "सिंचाई का फैसला: {action}।",
        "gu": "સિંચાઈનો નિર્ણય: {action}.",
    },
    "irrigation_reason": {
        "en": "Reason: {reason}",
        "hi": "कारण: {reason}",
        "gu": "કારણ: {reason}",
    },
    "soil_moisture_line": {
        "en": "Soil moisture was {m}% (dry threshold 30%, ideal band 30-75%).",
        "hi": "मिट्टी की नमी {m}% थी (सूखे की सीमा 30%, आदर्श 30-75%)।",
        "gu": "માટીમાં ભેજ {m}% હતો (સૂકી સીમા 30%, આદર્શ 30-75%).",
    },
    "no_irrigation": {
        "en": "No irrigation assessment is available in this session yet - enter soil moisture "
              "(and ideally a city) and press Analyze.",
        "hi": "इस सत्र में अभी सिंचाई का आकलन नहीं है - मिट्टी की नमी (और हो सके तो शहर) भरकर "
              "'विश्लेषण' दबाएँ।",
        "gu": "આ સત્રમાં હજી સિંચાઈનું મૂલ્યાંકન નથી - માટીનો ભેજ (અને શક્ય હોય તો શહેર) ભરીને "
              "'વિશ્લેષણ' દબાવો.",
    },
    "sensors_line": {
        "en": "The simulated sensor feed currently reports soil moisture {m}% at {t}C.",
        "hi": "सिम्युलेटेड सेंसर अभी मिट्टी की नमी {m}% और तापमान {t}°C बता रहा है।",
        "gu": "સિમ્યુલેટેડ સેન્સર હાલ માટીનો ભેજ {m}% અને તાપમાન {t}°C બતાવે છે.",
    },
    "weather_live": {
        "en": "Live weather for {city}: {cond}, {t}C, humidity {h}%, wind {w} km/h. Rain "
              "probability today {p}% and about {mm} mm expected over the week.",
        "hi": "{city} का ताज़ा मौसम: {cond}, {t}°C, आर्द्रता {h}%, हवा {w} किमी/घंटा। आज बारिश "
              "की संभावना {p}% और सप्ताह में लगभग {mm} मिमी।",
        "gu": "{city}નું તાજું હવામાન: {cond}, {t}°C, ભેજ {h}%, પવન {w} કિમી/કલાક. આજે વરસાદની "
              "સંભાવના {p}% અને અઠવાડિયામાં લગભગ {mm} મિમી.",
    },
    "weather_offline_extra": {
        "en": "I will not invent a forecast; the analysis used the values you typed.",
        "hi": "मैं मौसम का अंदाज़ा नहीं गढ़ूँगा; विश्लेषण में आपके भरे मान ही लगे हैं।",
        "gu": "હું હવામાનની અટકળ નહીં કરું; વિશ્લેષણમાં તમે ભરેલા મૂલ્યો જ વપરાયા છે.",
    },
    "no_weather": {
        "en": "No weather data in this session - add a city (or allow location) and press Analyze.",
        "hi": "इस सत्र में मौसम डेटा नहीं है - शहर जोड़ें (या लोकेशन दें) और 'विश्लेषण' दबाएँ।",
        "gu": "આ સત્રમાં હવામાનનો ડેટા નથી - શહેર ઉમેરો (અથવા લોકેશન આપો) અને 'વિશ્લેષણ' દબાવો.",
    },
    "sus_index": {
        "en": "AgriSmart Sustainability Index: {total}/100 (grade {grade}, {band}). Formula: {formula}.",
        "hi": "एग्रीस्मार्ट टिकाऊपन सूचकांक: {total}/100 (ग्रेड {grade}, {band})। सूत्र: {formula}।",
        "gu": "એગ્રીસ્માર્ટ ટકાઉપણ સૂચકાંક: {total}/100 (ગ્રેડ {grade}, {band}). સૂત્ર: {formula}.",
    },
    "sus_subscores": {
        "en": "Sub-scores: {list}.",
        "hi": "उप-स्कोर: {list}।",
        "gu": "ઉપ-સ્કોર: {list}.",
    },
    "sus_weakest": {
        "en": "The weakest lever is {area}{reason}. Tip: {tip}",
        "hi": "सबसे कमज़ोर पहलू {area}{reason} है। सुझाव: {tip}",
        "gu": "સૌથી નબળું પાસું {area}{reason} છે. સૂચન: {tip}",
    },
    "no_sus": {
        "en": "The sustainability score is produced together with an analysis - run Analyze and I "
              "can break it down line by line.",
        "hi": "टिकाऊपन स्कोर विश्लेषण के साथ ही बनता है - 'विश्लेषण' चलाएँ, फिर मैं इसे पंक्ति-दर-पंक्ति "
              "समझाऊँगा।",
        "gu": "ટકાઉપણ સ્કોર વિશ્લેષણ સાથે જ બને છે - 'વિશ્લેષણ' ચલાવો, પછી હું તેને લાઇન-બાય-લાઇન "
              "સમજાવીશ.",
    },
    "crop_rank": {
        "en": "For the soil and climate you entered, the RandomForest ranks: {list}.",
        "hi": "आपकी मिट्टी और जलवायु के लिए रैंडम फ़ॉरेस्ट का क्रम: {list}।",
        "gu": "તમારી માટી અને હવામાન માટે રેન્ડમ ફોરેસ્ટનો ક્રમ: {list}.",
    },
    "no_crop": {
        "en": "I need N, P, K, pH, temperature, humidity and rainfall to suggest a crop - fill the "
              "crop-recommendation panel and I will rank the top three.",
        "hi": "फसल सुझाने के लिए मुझे N, P, K, pH, तापमान, आर्द्रता और वर्षा चाहिए - फसल-सुझाव "
              "पैनल भरें, मैं शीर्ष तीन का क्रम बताऊँगा।",
        "gu": "પાક સૂચવવા માટે મને N, P, K, pH, તાપમાન, ભેજ અને વરસાદ જોઈએ - પાક-સૂચન પેનલ ભરો, "
              "હું ટોચના ત્રણનો ક્રમ કહીશ.",
    },
    "general_intro": {
        "en": "Here is what this session already established: {bits}.",
        "hi": "इस सत्र में अब तक यह पता चला है: {bits}।",
        "gu": "આ સત્રમાં અત્યાર સુધી આ જાણવા મળ્યું: {bits}.",
    },
    "general_bits_none": {
        "en": "no disease prediction yet",
        "hi": "अभी रोग का कोई पूर्वानुमान नहीं",
        "gu": "હજી રોગની કોઈ આગાહી નથી",
    },
    "general_bits_risk": {
        "en": " at {risk} risk",
        "hi": ", जोखिम {risk}",
        "gu": ", જોખમ {risk}",
    },
    "general_bits_irrigation": {
        "en": "; irrigation says {action}",
        "hi": "; सिंचाई कहती है: {action}",
        "gu": "; સિંચાઈ કહે છે: {action}",
    },
    "general_bits_sus": {
        "en": "; field health index {total}/100",
        "hi": "; खेत-स्वास्थ्य सूचकांक {total}/100",
        "gu": "; ખેત-આરોગ્ય સૂચકાંક {total}/100",
    },
    "risk_unreported": {
        "en": "an unreported",
        "hi": "अज्ञात",
        "gu": "અજાણ્યા",
    },
    "weather_here": {
        "en": "this location",
        "hi": "इस स्थान",
        "gu": "આ સ્થળ",
    },
    "general_hint": {
        "en": "Ask me about the disease, treatment, irrigation, weather, the sustainability score "
              "or which crop to plant next.",
        "hi": "मुझसे रोग, इलाज, सिंचाई, मौसम, टिकाऊपन स्कोर या अगली फसल के बारे में पूछें।",
        "gu": "મને રોગ, ઉપાય, સિંચાઈ, હવામાન, ટકાઉપણ સ્કોર કે આગળનો પાક પૂછો.",
    },
    # sustainability vocabulary (the ASI module publishes English band words)
    "band_excellent": {"en": "excellent", "hi": "उत्तम", "gu": "ઉત્તમ"},
    "band_good": {"en": "good", "hi": "अच्छा", "gu": "સારું"},
    "band_fair": {"en": "fair", "hi": "ठीक-ठाक", "gu": "મધ્યમ"},
    "band_poor": {"en": "poor", "hi": "कमज़ोर", "gu": "નબળું"},
    "band_critical": {"en": "critical", "hi": "गंभीर", "gu": "ગંભીર"},
    "sub_water": {"en": "water", "hi": "पानी", "gu": "પાણી"},
    "sub_weather": {"en": "weather", "hi": "मौसम", "gu": "હવામાન"},
    "sub_disease": {"en": "disease", "hi": "रोग", "gu": "રોગ"},
    "sub_resource": {"en": "resource", "hi": "संसाधन", "gu": "સાધન-સંસાધન"},

    # provenance chips shown under the answer
    "src_prediction": {
        "en": "crop-disease model output",
        "hi": "फसल-रोग मॉडल का नतीजा",
        "gu": "પાક-રોગ મોડેલનું પરિણામ",
    },
    "src_risk": {
        "en": "AgriSmart knowledge base (KB v1)",
        "hi": "एग्रीस्मार्ट ज्ञानकोश (KB v1)",
        "gu": "એગ્રીસ્માર્ટ જ્ઞાનકોશ (KB v1)",
    },
    "src_irrigation": {
        "en": "irrigation rule engine (modules/weather.py)",
        "hi": "सिंचाई नियम-इंजन",
        "gu": "સિંચાઈ નિયમ-એન્જિન",
    },
    "src_weather": {
        "en": "Open-Meteo live weather (or manual input when offline)",
        "hi": "Open-Meteo लाइव मौसम (ऑफ़लाइन होने पर मैन्युअल मान)",
        "gu": "Open-Meteo લાઇવ હવામાન (ઑફલાઇન હોય તો મેન્યુઅલ મૂલ્યો)",
    },
    "src_sustainability": {
        "en": "AgriSmart Sustainability Index formula",
        "hi": "एग्रीस्मार्ट टिकाऊपन सूचकांक सूत्र",
        "gu": "એગ્રીસ્માર્ટ ટકાઉપણ સૂચકાંક સૂત્ર",
    },
    "src_crop": {
        "en": "RandomForest crop-recommendation model (Bonus A)",
        "hi": "रैंडम फ़ॉरेस्ट फसल-सुझाव मॉडल (बोनस A)",
        "gu": "રેન્ડમ ફોરેસ્ટ પાક-સૂચન મોડેલ (બોનસ A)",
    },
    "src_sensors": {
        "en": "simulated IoT sensor feed (modules/iot_sim.py)",
        "hi": "सिम्युलेटेड IoT सेंसर फ़ीड",
        "gu": "સિમ્યુલેટેડ IoT સેન્સર ફીડ",
    },
}

# --- crop and disease vocabulary -------------------------------------------- #
# The knowledge base and the model's class list are English, so the *noun* inside
# the sentence is swapped for the local word rather than translating whole names.
CROP_NAMES: dict[str, dict[str, str]] = {
    "apple": {"hi": "सेब", "gu": "સેબ"},
    "blueberry": {"hi": "ब्लूबेरी", "gu": "બ્લૂબેરી"},
    "cherry": {"hi": "चेरी", "gu": "ચેરી"},
    "corn": {"hi": "मक्का", "gu": "મકાઈ"},
    "maize": {"hi": "मक्का", "gu": "મકાઈ"},
    "grape": {"hi": "अंगूर", "gu": "દ્રાક્ષ"},
    "orange": {"hi": "संतरा", "gu": "નારંગી"},
    "peach": {"hi": "आड़ू", "gu": "આલૂ"},
    "pepper, bell": {"hi": "शिमला मिर्च", "gu": "શિમલા મરચું"},
    "bell pepper": {"hi": "शिमला मिर्च", "gu": "શિમલા મરચું"},
    "potato": {"hi": "आलू", "gu": "બટાકા"},
    "raspberry": {"hi": "रास्पबेरी", "gu": "રાસ્પબેરી"},
    "soybean": {"hi": "सोयाबीन", "gu": "સોયાબીન"},
    "strawberry": {"hi": "स्ट्रॉबेरी", "gu": "સ્ટ્રોબેરી"},
    "citrus": {"hi": "सिट्रस", "gu": "સિટ્રસ"},
    "squash": {"hi": "कद्दू-वर्गीय सब्ज़ी", "gu": "કોળું-વર્ગની શાકભાજી"},
    "tomato": {"hi": "टमाटर", "gu": "ટામેટું"},
    # the crop-recommendation model's 22 crops (Bonus A)
    "rice": {"hi": "धान", "gu": "ડાંગર"},
    "wheat": {"hi": "गेहूँ", "gu": "ઘઉં"},
    "chickpea": {"hi": "चना", "gu": "ચણા"},
    "kidneybeans": {"hi": "राजमा", "gu": "રાજમા"},
    "pigeonpeas": {"hi": "अरहर", "gu": "તુવેર"},
    "mothbeans": {"hi": "मोठ", "gu": "મઠ"},
    "mungbean": {"hi": "मूँग", "gu": "મગ"},
    "blackgram": {"hi": "उड़द", "gu": "અડદ"},
    "lentil": {"hi": "मसूर", "gu": "મસૂર"},
    "pomegranate": {"hi": "अनार", "gu": "દાડમ"},
    "banana": {"hi": "केला", "gu": "કેળું"},
    "mango": {"hi": "आम", "gu": "કેરી"},
    "grapes": {"hi": "अंगूर", "gu": "દ્રાક્ષ"},
    "watermelon": {"hi": "तरबूज़", "gu": "તરબૂચ"},
    "muskmelon": {"hi": "खरबूज़ा", "gu": "શક્કરટેટી"},
    "cotton": {"hi": "कपास", "gu": "કપાસ"},
    "jute": {"hi": "जूट", "gu": "શણ"},
    "coffee": {"hi": "कॉफ़ी", "gu": "કોફી"},
    "coconut": {"hi": "नारियल", "gu": "નાળિયેર"},
    "papaya": {"hi": "पपीता", "gu": "પપૈયું"},
}

DISEASE_TERMS: dict[str, dict[str, str]] = {
    "healthy": {"hi": "स्वस्थ", "gu": "સ્વસ્થ"},
    "early blight": {"hi": "अगेती झुलसा", "gu": "વહેલો સુકારો"},
    "late blight": {"hi": "पिछेती झुलसा", "gu": "મોડો સુકારો"},
    "northern leaf blight": {"hi": "उत्तरी पत्ती झुलसा", "gu": "ઉત્તરીય પાન સુકારો"},
    "leaf blight": {"hi": "पत्ती झुलसा", "gu": "પાન સુકારો"},
    "bacterial spot": {"hi": "जीवाणु धब्बा", "gu": "બેક્ટેરિયલ ડાઘ"},
    "black rot": {"hi": "काला सड़न", "gu": "કાળો સડો"},
    "grey leaf spot": {"hi": "ग्रे पत्ती धब्बा", "gu": "ગ્રે પાન ડાઘ"},
    "gray leaf spot": {"hi": "ग्रे पत्ती धब्बा", "gu": "ગ્રે પાન ડાઘ"},
    "leaf spot": {"hi": "पत्ती धब्बा", "gu": "પાન ડાઘ"},
    "septoria leaf spot": {"hi": "सेप्टोरिया पत्ती धब्बा", "gu": "સેપ્ટોરિયા પાન ડાઘ"},
    "target spot": {"hi": "टारगेट धब्बा", "gu": "ટાર્ગેટ ડાઘ"},
    "common rust": {"hi": "सामान्य रतुआ", "gu": "સામાન્ય ગેરુ"},
    "rust": {"hi": "रतुआ", "gu": "ગેરુ"},
    "scab": {"hi": "पपड़ी रोग", "gu": "ખરડો રોગ"},
    "leaf mold": {"hi": "पत्ती फफूंद", "gu": "પાન ફૂગ"},
    "leaf mould": {"hi": "पत्ती फफूंद", "gu": "પાન ફૂગ"},
    "mosaic virus": {"hi": "मोज़ेक विषाणु", "gu": "મોઝેક વિષાણુ"},
    "yellow leaf curl virus": {"hi": "पीला पत्ती मरोड़ विषाणु", "gu": "પીળો પાન વળ વિષાણુ"},
    "haunglongbing": {"hi": "हरित रोग (HLB)", "gu": "હરિત રોગ (HLB)"},
    "esca": {"hi": "एस्का (अंगूर का तना रोग)", "gu": "એસ્કા (દ્રાક્ષનો થડ રોગ)"},
    "spider mites": {"hi": "मकड़ी के कीट", "gu": "માકડી જીવાત"},
    "bacterial": {"hi": "जीवाणुज", "gu": "બેક્ટેરિયલ"},
    # --- vocabulary added with the 38-class model ------------------------------ #
    "cedar apple rust": {"hi": "देवदार-सेब रतुआ", "gu": "દેવદાર-સેબ ગેરુ"},
    "powdery mildew": {"hi": "चूर्णिल आसिता", "gu": "ભૂકી ફૂગ"},
    "greening": {"hi": "हरित रोग (HLB)", "gu": "હરિયાળું રોગ (HLB)"},
    "citrus greening": {"hi": "सिट्रस हरित रोग", "gu": "સિટ્રસ હરિયાળું રોગ"},
    "spider mite": {"hi": "मकड़ी कीट", "gu": "મકોડ જીવાત"},
    "two-spotted spider mite": {"hi": "दो-धब्बा मकड़ी कीट", "gu": "બે-ટપકાંવાળી મકોડ"},
    "septoria": {"hi": "सेप्टोरिया", "gu": "સેપ્ટોરિયા"},
    "leaf scorch": {"hi": "पत्ती झुलसन", "gu": "પાન બળવું"},
}


def say(key: str, lang: str | None = None, **fmt: Any) -> str:
    """Render a template. Unknown keys/format problems fall back to English."""
    row = PHRASES.get(key)
    if not row:
        return key
    tag = (lang or "en").lower()[:2] if lang else "en"
    if tag not in LANGS:
        tag = "en"
    text = row.get(tag) or row["en"]
    try:
        return text.format(**fmt) if fmt else text
    except (KeyError, IndexError):
        return text


# Plant parts that appear inside KB condition names ("Healthy apple leaf").
# Applied *after* the disease terms so "grey leaf spot" keeps its own translation.
PLANT_PARTS: dict[str, dict[str, str]] = {
    "leaf": {"hi": "पत्ती", "gu": "પાન"},
    "leaves": {"hi": "पत्तियाँ", "gu": "પાન"},
}


def _kb_crops() -> dict[str, dict[str, str]]:
    """The knowledge base owns the crop names - reuse them so the app speaks with
    one voice ('ટામેટું' from the KB, not a second spelling invented here)."""
    try:
        from .recommendations import CROPS
        return CROPS
    except Exception:  # pragma: no cover - KB always ships, but never hard-fail
        return {}


def _crop_words() -> dict[str, dict[str, str]]:
    """English crop word -> local word, KB names taking precedence over ours.

    Without this the same sentence could mix two spellings of one crop (the KB's
    'ટામેટું' next to a second guess from CROP_NAMES); with it, the KB always wins.
    """
    words = {en: {"hi": row["hi"], "gu": row["gu"]}
             for en, row in _kb_crops().items() if row.get("hi") and row.get("gu")}
    kb_names = {row["en"]: {"hi": row["hi"], "gu": row["gu"]}
                for row in _kb_crops().values() if row.get("en")}
    for en, row in CROP_NAMES.items():
        words.setdefault(en, row)
    words.update(kb_names)
    return words


BAND_KEYS = {"excellent": "band_excellent", "good": "band_good", "fair": "band_fair",
             "poor": "band_poor", "critical": "band_critical"}
SUBSCORE_KEYS = {"water": "sub_water", "weather": "sub_weather",
                 "disease": "sub_disease", "resource": "sub_resource"}


def localize_band(word: str | None, lang: str | None = None) -> str:
    """'Good' -> 'सारा'/'સારું'. English passes through unchanged (byte-stable)."""
    if not word:
        return ""
    if not lang or lang == "en":
        return str(word)
    key = BAND_KEYS.get(str(word).strip().lower())
    return say(key, lang) if key else str(word)


def localize_subscore(key: str, lang: str | None = None) -> str:
    if not lang or lang == "en":
        return key
    return say(SUBSCORE_KEYS.get(key, ""), lang) or key


def canonical(text: str | None) -> str | None:
    """Any localized form -> the English form, so re-localisation is safe."""
    if not text:
        return text
    out = str(text)
    for table in (_kb_crops(), _crop_words(), CROP_NAMES, DISEASE_TERMS, PLANT_PARTS):
        for en, row in table.items():
            for lang in ("hi", "gu"):
                local = row.get(lang)
                if local and local != en and local in out:
                    out = out.replace(local, en)
    return out


def _swap(text: str, table: dict[str, dict[str, str]], lang: str) -> str:
    """Replace English nouns with local ones, longest phrase first."""
    for word in sorted(table, key=len, reverse=True):
        local = table[word].get(lang)
        if not local:
            continue
        text = re.sub(rf"\b{re.escape(word)}\b", local, text, flags=re.I)
    return text


def localize_condition(text: str | None, lang: str | None = None) -> str | None:
    """'Tomato late blight (Phytophthora infestans)' -> 'टमाटर मोडो सुकारो (Phytophthora infestans)'.

    The scientific name in brackets is deliberately left alone - it is the same in
    every language and it is what a lab or agri-officer will look for.
    """
    if not text:
        return text
    out = canonical(text)                     # mixed-language contexts are safe
    if not lang or lang == "en":
        return out
    out = _swap(out, _crop_words(), lang)
    out = _swap(out, DISEASE_TERMS, lang)
    out = _swap(out, PLANT_PARTS, lang)      # last: bare "leaf" only
    return out


def localize_crop(text: str | None, lang: str | None = None) -> str | None:
    if not text:
        return text
    out = canonical(text)
    if not lang or lang == "en":
        return out
    # a bare slug ("tomato", "bell_pepper") maps exactly through the KB table
    slug = str(out).strip().lower().replace(" ", "_")
    entry = _kb_crops().get(slug)
    if entry:
        return entry.get(lang) or entry.get("en") or out
    return _swap(out, _crop_words(), lang)


def localize_source(label: str, lang: str | None = None) -> str:
    """Map the internal provenance label onto a localized chip."""
    key = {
        "crop-disease model output": "src_prediction",
        "AgriSmart knowledge base (KB v1)": "src_risk",
        "irrigation rule engine": "src_irrigation",
        "Open-Meteo live weather (or manual input when offline)": "src_weather",
        "AgriSmart Sustainability Index formula": "src_sustainability",
        "RandomForest crop-recommendation model (Bonus A)": "src_crop",
        "simulated IoT sensor feed (modules/iot_sim.py)": "src_sensors",
    }.get(label)
    rendered = say(key, lang) if key else label
    return rendered


def checks() -> list[str]:
    """Template ids missing a translation (empty list == fully localised)."""
    out = []
    for key, row in PHRASES.items():
        for lang in LANGS:
            if not row.get(lang):
                out.append(f"{key}:{lang}")
    for word, row in {**CROP_NAMES, **DISEASE_TERMS, **PLANT_PARTS}.items():
        for lang in ("hi", "gu"):
            if not row.get(lang):
                out.append(f"vocab:{word}:{lang}")
    return sorted(out)
