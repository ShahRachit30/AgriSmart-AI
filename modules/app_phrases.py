"""App-wide prose in English / Hindi / Gujarati.

`modules/assistant_i18n.py` localises the *assistant's* sentences and the crop and
disease vocabulary. This module does the same job for everything the rest of the API
says: irrigation reasons and alerts, the WMO weather words, the sustainability
reason lines and tips, risk notes, the analysis narrative, crop-advice lines, sensor
labels and metric descriptions.

Rule of thumb: if a user can read it, it is in here in all three languages.
`checks()` lists rows missing a language and the test suite fails when it is not
empty, so adding a new sentence without translations breaks the build rather than
silently shipping English to a Gujarati farmer.
"""
from __future__ import annotations

from typing import Any

LANGS = ("en", "hi", "gu")

PHRASES: dict[str, dict[str, str]] = {
    # ---------------------------------------------------------------- weather --
    "w_no_data": {
        "en": "No soil-moisture or rain-probability input available - defaulting to MONITOR and "
              "recommending a manual soil check.",
        "hi": "मिट्टी की नमी या बारिश की संभावना का कोई इनपुट नहीं - इसलिए 'निगरानी' चुना गया है; "
              "कृपया मिट्टी की जाँच स्वयं करें।",
        "gu": "માટીનો ભેજ કે વરસાદની સંભાવનાનું કોઈ ઇનપુટ નથી - તેથી 'નજર રાખો' પસંદ કર્યું છે; "
              "કૃપા કરીને માટીની તપાસ જાતે કરો.",
    },
    "w_rain_delay": {
        "en": "Rain probability {rain} % (>= {thr} %) - irrigation would be wasted and can waterlog "
              "the root zone.",
        "hi": "बारिश की संभावना {rain}% (>= {thr}%) - सिंचाई बेकार जाएगी और जड़ें गल सकती हैं।",
        "gu": "વરસાદની સંભાવના {rain}% (>= {thr}%) - સિંચાઈ નકામી જશે અને મૂળ ગળી શકે છે.",
    },
    "w_soil_dry": {
        "en": "Soil moisture {soil} % is below the {thr} % dry threshold and rain is unlikely "
              "({rain} %).",
        "hi": "मिट्टी की नमी {soil}% है, जो {thr}% की सूखी सीमा से कम है, और बारिश की संभावना कम है "
              "({rain}%)।",
        "gu": "માટીનો ભેજ {soil}% છે, જે {thr}% સૂકી સીમાથી ઓછો છે, અને વરસાદની સંભાવના ઓછી છે "
              "({rain}%).",
    },
    "w_watch_band": {
        "en": "Rain probability {rain} % is in the {lo}-{hi} % watch band - re-check in 12 h before "
              "irrigating.",
        "hi": "बारिश की संभावना {rain}% {lo}-{hi}% की निगरानी सीमा में है - सिंचाई से पहले 12 घंटे "
              "बाद दोबारा देखें।",
        "gu": "વરસાદની સંભાવના {rain}% {lo}-{hi}% ની દેખરેખ શ્રેણીમાં છે - સિંચાઈ પહેલાં 12 કલાક "
              "પછી ફરી તપાસો.",
    },
    "w_low_rain": {
        "en": "Soil moisture {soil} % is low but rain is plausible - monitor instead of irrigating.",
        "hi": "मिट्टी की नमी {soil}% कम है, पर बारिश की गुंजाइश है - सिंचाई करने के बजाय निगरानी रखें।",
        "gu": "માટીનો ભેજ {soil}% ઓછો છે, પણ વરસાદની શક્યતા છે - સિંચાઈ કરવાને બદલે નજર રાખો.",
    },
    "w_adequate": {
        "en": "Soil moisture {soil} % is adequate - no irrigation needed.",
        "hi": "मिट्टी की नमी {soil}% पर्याप्त है - सिंचाई की ज़रूरत नहीं।",
        "gu": "માટીનો ભેજ {soil}% પૂરતો છે - સિંચાઈની જરૂર નથી.",
    },
    "w_partial": {
        "en": "Only partial data available - monitor the field and re-run with a soil reading.",
        "hi": "केवल आंशिक जानकारी उपलब्ध है - खेत पर नज़र रखें और मिट्टी की रीडिंग के साथ दोबारा "
              "चलाएँ।",
        "gu": "ફક્ત આંશિક માહિતી ઉપલબ્ધ છે - ખેતર પર નજર રાખો અને માટીની રીડિંગ સાથે ફરી ચલાવો.",
    },
    "w_split": {
        "en": "Because of the heat, prefer a split irrigation (early morning + evening).",
        "hi": "गर्मी के कारण सिंचाई बाँटकर करें (सुबह जल्दी + शाम को)।",
        "gu": "ગરમીને કારણે સિંચાઈ વહેંચીને કરો (વહેલી સવારે + સાંજે).",
    },
    "w_rain_refill": {
        "en": "{mm} mm rain recorded today - the soil profile is being refilled.",
        "hi": "आज {mm} मिमी बारिश दर्ज हुई - मिट्टी में नमी फिर भर रही है।",
        "gu": "આજે {mm} મિમી વરસાદ નોંધાયો - માટીમાં ભેજ ફરી ભરાઈ રહ્યો છે.",
    },
    "w_alert_heat": {
        "en": "Heat stress: {t} C max - irrigate early morning or after sunset to cut evaporation loss.",
        "hi": "गर्मी का तनाव: अधिकतम {t}°C - वाष्पीकरण कम करने के लिए सुबह जल्दी या सूरज ढलने के "
              "बाद सिंचाई करें।",
        "gu": "ગરમીનો તણાવ: મહત્તમ {t}°C - બાષ્પીભવન ઘટાડવા વહેલી સવારે કે સૂર્યાસ્ત પછી સિંચાઈ કરો.",
    },
    "w_alert_frost": {
        "en": "Frost risk: {t} C min - cover nursery beds and light-irrigate before sunset "
              "(protects roots).",
        "hi": "पाले का खतरा: न्यूनतम {t}°C - नर्सरी क्यारियाँ ढकें और सूरज ढलने से पहले हल्की सिंचाई "
              "करें (जड़ों की सुरक्षा)।",
        "gu": "હિમનો ભય: ન્યૂનતમ {t}°C - નર્સરી પાત્રો ઢાંકો અને સૂર્યાસ્ત પહેલાં હળવી સિંચાઈ કરો "
              "(મૂળનું રક્ષણ).",
    },
    "w_alert_humid": {
        "en": "High humidity {rh} % - fungal pressure is up; keep canopy dry and re-inspect leaves "
              "in 3-4 days.",
        "hi": "अधिक आर्द्रता {rh}% - फफूंद का खतरा बढ़ा है; पत्ते सूखे रखें और 3-4 दिन बाद फिर जाँचें।",
        "gu": "વધુ ભેજ {rh}% - ફૂગનું જોખમ વધ્યું છે; પાન સૂકા રાખો અને 3-4 દિવસ પછી ફરી તપાસો.",
    },
    "w_alert_severe": {
        "en": "Severe weather now: {cond} - avoid spraying.",
        "hi": "अभी गंभीर मौसम: {cond} - छिड़काव से बचें।",
        "gu": "હાલ ગંભીર હવામાન: {cond} - છંટકાવ ટાળો.",
    },
    # ---------------------------------------------- WMO weather interpretation --
    "wcode_0": {"en": "Clear sky", "hi": "साफ़ आसमान", "gu": "સ્વચ્છ આકાશ"},
    "wcode_1": {"en": "Mainly clear", "hi": "ज़्यादातर साफ़", "gu": "મોટે ભાગે સ્વચ્છ"},
    "wcode_2": {"en": "Partly cloudy", "hi": "आंशिक बादल", "gu": "આંશિક વાદળ"},
    "wcode_3": {"en": "Overcast", "hi": "घने बादल", "gu": "ઘેરા વાદળ"},
    "wcode_45": {"en": "Fog", "hi": "कोहरा", "gu": "ધુમ્મસ"},
    "wcode_48": {"en": "Depositing rime fog", "hi": "जमा देने वाला कोहरा", "gu": "જામી જતું ધુમ્મસ"},
    "wcode_51": {"en": "Light drizzle", "hi": "हल्की फुहार", "gu": "હળવી ઝરમર"},
    "wcode_53": {"en": "Moderate drizzle", "hi": "मध्यम फुहार", "gu": "મધ્યમ ઝરમર"},
    "wcode_55": {"en": "Dense drizzle", "hi": "घनी फुहार", "gu": "ઘટ્ટ ઝરમર"},
    "wcode_56": {"en": "Light freezing drizzle", "hi": "हल्की जमने वाली फुहार", "gu": "હળવી થિજાવતી ઝરમર"},
    "wcode_57": {"en": "Dense freezing drizzle", "hi": "घनी जमने वाली फुहार", "gu": "ઘટ્ટ થિજાવતી ઝરમર"},
    "wcode_61": {"en": "Slight rain", "hi": "हल्की बारिश", "gu": "હળવો વરસાદ"},
    "wcode_63": {"en": "Moderate rain", "hi": "मध्यम बारिश", "gu": "મધ્યમ વરસાદ"},
    "wcode_65": {"en": "Heavy rain", "hi": "भारी बारिश", "gu": "ભારે વરસાદ"},
    "wcode_66": {"en": "Light freezing rain", "hi": "हल्की जमने वाली बारिश", "gu": "હળવો થિજાવતો વરસાદ"},
    "wcode_67": {"en": "Heavy freezing rain", "hi": "भारी जमने वाली बारिश", "gu": "ભારે થિજાવતો વરસાદ"},
    "wcode_71": {"en": "Slight snowfall", "hi": "हल्की बर्फ़बारी", "gu": "હળવો હિમવર્ષા"},
    "wcode_73": {"en": "Moderate snowfall", "hi": "मध्यम बर्फ़बारी", "gu": "મધ્યમ હિમવર્ષા"},
    "wcode_75": {"en": "Heavy snowfall", "hi": "भारी बर्फ़बारी", "gu": "ભારે હિમવર્ષા"},
    "wcode_77": {"en": "Snow grains", "hi": "बर्फ़ के कण", "gu": "હિમના કણ"},
    "wcode_80": {"en": "Slight rain showers", "hi": "हल्की बौछारें", "gu": "હળવા વરસાદના ઝાપટાં"},
    "wcode_81": {"en": "Moderate rain showers", "hi": "मध्यम बौछारें", "gu": "મધ્યમ ઝાપટાં"},
    "wcode_82": {"en": "Violent rain showers", "hi": "तेज़ बौछारें", "gu": "ભારે ઝાપટાં"},
    "wcode_85": {"en": "Slight snow showers", "hi": "हल्की बर्फ़ की बौछारें", "gu": "હળવા હિમવર્ષાના ઝાપટાં"},
    "wcode_86": {"en": "Heavy snow showers", "hi": "भारी बर्फ़ की बौछारें", "gu": "ભારે હિમવર્ષાના ઝાપટાં"},
    "wcode_95": {"en": "Thunderstorm", "hi": "आंधी-तूफ़ान", "gu": "વીજળી સાથે તોફાન"},
    "wcode_96": {"en": "Thunderstorm with slight hail", "hi": "हल्के ओले के साथ तूफ़ान", "gu": "હળવા કરા સાથે તોફાન"},
    "wcode_99": {"en": "Thunderstorm with heavy hail", "hi": "भारी ओले के साथ तूफ़ान", "gu": "ભારે કરા સાથે તોફાન"},
    # -------------------------------------------------------- risk card notes --
    "r_healthy": {
        "en": "The model sees a healthy leaf. Keep scouting weekly - detection is cheaper than cure.",
        "hi": "मॉडल के अनुसार पत्ती स्वस्थ है। हर हफ़्ते निरीक्षण करते रहें - रोग पकड़ना इलाज से सस्ता है।",
        "gu": "મોડેલ મુજબ પાન સ્વસ્થ છે. દર અઠવાડિયે નિરીક્ષણ કરતા રહો - રોગ પકડવો ઉપાય કરતાં સસ્તો છે.",
    },
    "r_conf_high": {
        "en": "Confidence {conf} is above the {thr} threshold, so the knowledge-base severity is "
              "reported unchanged.",
        "hi": "भरोसा {conf} {thr} की सीमा से ऊपर है, इसलिए ज्ञानकोश की गंभीरता जैसी है वैसी बताई गई है।",
        "gu": "ભરોસો {conf} {thr} ની સીમાથી ઉપર છે, તેથી જ્ઞાનકોશની ગંભીરતા જેવી છે તેવી જણાવી છે.",
    },
    "r_conf_mid": {
        "en": "Confidence {conf} is in the {lo}-{hi} band: treat this as a suspect case, confirm "
              "visually and re-photograph before buying chemicals.",
        "hi": "भरोसा {conf} {lo}-{hi} के बीच है: इसे संदिग्ध मानें, आँखों से पुष्टि करें और दवा खरीदने "
              "से पहले नई फोटो लें।",
        "gu": "ભરોસો {conf} {lo}-{hi} વચ્ચે છે: આને શંકાસ્પદ ગણો, આંખે ખાતરી કરો અને દવા ખરીદતા "
              "પહેલાં નવો ફોટો લો.",
    },
    "r_humid": {
        "en": "Humid/rainy conditions favour sporulation: risk upgraded one step.",
        "hi": "नम/बरसाती मौसम में फफूंद फैलती है: जोखिम एक स्तर बढ़ाया गया।",
        "gu": "ભેજવાળું/વરસાદી હવામાન ફૂગ ફેલાવે છે: જોખમ એક સ્તર વધાર્યું.",
    },
    "r_source": {
        "en": "AgriSmart KB v1 (ICAR/extension practice)",
        "hi": "एग्रीस्मार्ट ज्ञानकोश v1 (ICAR/प्रसार पद्धति)",
        "gu": "એગ્રીસ્માર્ટ જ્ઞાનકોશ v1 (ICAR/પ્રસાર પદ્ધતિ)",
    },
    "a_scout_only": {
        "en": "No treatment needed now - scout weekly and keep foliage dry overnight.",
        "hi": "अभी इलाज की ज़रूरत नहीं - हर हफ़्ते निरीक्षण करें और रात में पत्ते सूखे रखें।",
        "gu": "હાલ ઉપાયની જરૂર નથી - દર અઠવાડિયે નિરીક્ષણ કરો અને રાત્રે પાન સૂકા રાખો.",
    },
    "a_chem_strong": {
        "en": "If the organic route is not enough: {product} - {dose}. {note}",
        "hi": "जैविक उपाय काफ़ी न हों तो: {product} - {dose}. {note}",
        "gu": "જૈવિક ઉપાય પૂરતા ન થાય તો: {product} - {dose}. {note}",
    },
    "a_chem_mild": {
        "en": "Chemical escalation option (only if symptoms spread): {product} - {dose}.",
        "hi": "रासायनिक विकल्प (सिर्फ़ लक्षण फैलने पर): {product} - {dose}.",
        "gu": "રાસાયણિક વિકલ્પ (ફક્ત લક્ષણ ફેલાય તો): {product} - {dose}.",
    },
    # ------------------------------------------------- sustainability reasons --
    "s_moisture_unknown": {
        "en": "Soil moisture unknown (-15): add a reading or connect a sensor for a sharper score.",
        "hi": "मिट्टी की नमी अज्ञात (-15): सटीक स्कोर के लिए रीडिंग दें या सेंसर जोड़ें।",
        "gu": "માટીનો ભેજ અજાણ (-15): સચોટ સ્કોર માટે રીડિંગ આપો કે સેન્સર જોડો.",
    },
    "s_soil_dry": {
        "en": "Soil moisture {m} % is below the 30 % dry threshold (-{pen:.0f}).",
        "hi": "मिट्टी की नमी {m}% 30% की सूखी सीमा से कम है (-{pen:.0f})।",
        "gu": "માટીનો ભેજ {m}% 30% સૂકી સીમાથી ઓછો છે (-{pen:.0f}).",
    },
    "s_soil_wet": {
        "en": "Soil moisture {m} % is above 75 % (waterlogging risk, -{pen:.0f}).",
        "hi": "मिट्टी की नमी {m}% 75% से ऊपर है (जलभराव का खतरा, -{pen:.0f})।",
        "gu": "માટીનો ભેજ {m}% 75% થી ઉપર છે (પાણી ભરાવાનું જોખમ, -{pen:.0f}).",
    },
    "s_soil_ideal": {
        "en": "Soil moisture {m} % sits in the 30-75 % ideal band (no penalty).",
        "hi": "मिट्टी की नमी {m}% 30-75% के आदर्श दायरे में है (कोई कटौती नहीं)।",
        "gu": "માટીનો ભેજ {m}% 30-75% ના આદર્શ દાયરામાં છે (કોઈ કપાત નથી).",
    },
    "s_delayed_ok": {
        "en": "Irrigation correctly delayed ahead of rain (+5).",
        "hi": "बारिश के अनुमान से सिंचाई ठीक से टाली गई (+5)।",
        "gu": "વરસાદના અનુમાનથી સિંચાઈ યોગ્ય રીતે મુલતવી રાખી (+5).",
    },
    "s_irrigating_in_rain": {
        "en": "Irrigating while it is raining wastes water (-8).",
        "hi": "बारिश में सिंचाई करना पानी की बर्बादी है (-8)।",
        "gu": "વરસાદમાં સિંચાઈ કરવી પાણીનો બગાડ છે (-8).",
    },
    "s_rain_fungal": {
        "en": "Rain probability {rain} % favours fungal spread (-8).",
        "hi": "बारिश की संभावना {rain}% फफूंद फैलाने में मदद करती है (-8)।",
        "gu": "વરસાદની સંભાવના {rain}% ફૂગ ફેલાવવામાં મદદ કરે છે (-8).",
    },
    "s_rain_watch": {
        "en": "Rain probability {rain} % is a watch-level risk (-4).",
        "hi": "बारिश की संभावना {rain}% चेतावनी स्तर का जोखिम है (-4)।",
        "gu": "વરસાદની સંભાવના {rain}% ચેતવણી સ્તરનું જોખમ છે (-4).",
    },
    "s_humid_high": {
        "en": "Relative humidity {rh} % is high (-8).",
        "hi": "सापेक्ष आर्द्रता {rh}% अधिक है (-8)।",
        "gu": "સાપેક્ષ ભેજ {rh}% વધારે છે (-8).",
    },
    "s_humid_mid": {
        "en": "Relative humidity {rh} % is moderate (-4).",
        "hi": "सापेक्ष आर्द्रता {rh}% मध्यम है (-4)।",
        "gu": "સાપેક્ષ ભેજ {rh}% મધ્યમ છે (-4).",
    },
    "s_heat": {
        "en": "Heat stress at {t} C (-10).",
        "hi": "{t}°C पर गर्मी का तनाव (-10)।",
        "gu": "{t}°C પર ગરમીનો તણાવ (-10).",
    },
    "s_frost": {
        "en": "Frost risk at {t} C (-6).",
        "hi": "{t}°C पर पाले का खतरा (-6)।",
        "gu": "{t}°C પર હિમનો ભય (-6).",
    },
    "s_severe": {
        "en": "Severe weather at the moment of analysis (-12).",
        "hi": "विश्लेषण के समय गंभीर मौसम (-12)।",
        "gu": "વિશ્લેષણ સમયે ગંભીર હવામાન (-12).",
    },
    "s_live_weather": {
        "en": "Live weather (Open-Meteo) fed the decision (+6).",
        "hi": "निर्णय में लाइव मौसम (Open-Meteo) का उपयोग हुआ (+6)।",
        "gu": "નિર્ણયમાં લાઇવ હવામાન (Open-Meteo) વપરાયું (+6).",
    },
    "s_healthy_leaf": {
        "en": "Leaf classified healthy: no disease penalty.",
        "hi": "पत्ती स्वस्थ पाई गई: रोग के लिए कोई कटौती नहीं।",
        "gu": "પાન સ્વસ્થ મળ્યું: રોગ માટે કોઈ કપાત નથી.",
    },
    "s_disease": {
        "en": "Detected condition at '{risk}' risk (-{pen}). Treating it early is the sustainable "
              "choice; the penalty is for current field health, not for you.",
        "hi": "'{risk}' जोखिम पर रोग पाया गया (-{pen})। जल्दी इलाज करना ही टिकाऊ चुनाव है; यह कटौती "
              "अभी के खेत-स्वास्थ्य के लिए है, आपके लिए नहीं।",
        "gu": "'{risk}' જોખમ સ્તરે રોગ મળ્યો (-{pen}). વહેલો ઉપાય કરવો જ ટકાઉ પસંદ છે; આ કપાત હાલના "
              "ખેત-આરોગ્ય માટે છે, તમારા માટે નહીં.",
    },
    "s_chemical_on_table": {
        "en": "Chemical escalation is on the table for this risk level (-18); organic-first actions "
              "are listed before it.",
        "hi": "इस जोखिम स्तर पर रासायनिक विकल्प खुला है (-18); जैविक उपाय पहले दिए गए हैं।",
        "gu": "આ જોખમ સ્તરે રાસાયણિક વિકલ્પ ખુલ્લો છે (-18); જૈવિક ઉપાય પહેલાં આપ્યા છે.",
    },
    "s_organic_ok": {
        "en": "Organic-first route remains sufficient (+4).",
        "hi": "जैविक उपाय अब भी पर्याप्त हैं (+4)।",
        "gu": "જૈવિક ઉપાય હજી પૂરતા છે (+4).",
    },
    "s_crop_match": {
        "en": "The model's best-fit crop matches what is planted (+5).",
        "hi": "मॉडल की सबसे उपयुक्त फसल आपकी बोई फसल से मेल खाती है (+5)।",
        "gu": "મોડેલનો સૌથી યોગ્ય પાક તમે વાવેલા પાક સાથે મળે છે (+5).",
    },
    "s_crop_mismatch": {
        "en": "Model suggests {rec} over {planted} for the current conditions.",
        "hi": "मौजूदा हालात में मॉडल {planted} के बजाय {rec} सुझाता है।",
        "gu": "હાલની સ્થિતિમાં મોડેલ {planted} ને બદલે {rec} સૂચવે છે.",
    },
    "s_sensor_ok": {
        "en": "Sensor feed available: irrigation can be scheduled on data (+3).",
        "hi": "सेंसर फ़ीड उपलब्ध है: डेटा के आधार पर सिंचाई तय की जा सकती है (+3)।",
        "gu": "સેન્સર ફીડ ઉપલબ્ધ છે: ડેટા પરથી સિંચાઈ નક્કી કરી શકાય (+3).",
    },
    "s_area_large": {
        "en": "Farm of {area} ha makes uniform scouting harder (-3); consider zone-wise monitoring.",
        "hi": "{area} हेक्टेयर खेत में एक जैसी निगरानी कठिन है (-3); ज़ोन-वार निरीक्षण करें।",
        "gu": "{area} હેક્ટર ખેતરમાં એકસરખી દેખરેખ મુશ્કેલ છે (-3); ઝોન પ્રમાણે નિરીક્ષણ કરો.",
    },
    "s_tip_water": {
        "en": "Tighten irrigation scheduling (soil-moisture based) - the single biggest lever here.",
        "hi": "सिंचाई का समय मिट्टी की नमी के हिसाब से तय करें - यह सबसे बड़ा सुधार है।",
        "gu": "સિંચાઈનો સમય માટીના ભેજ પ્રમાણે નક્કી કરો - આ સૌથી મોટો સુધારો છે.",
    },
    "s_tip_weather": {
        "en": "Work with the forecast: protect the crop before a wet/cold spell instead of after.",
        "hi": "मौसम के पूर्वानुमान से चलें: भीगे/ठंडे दौर से पहले फसल बचाएँ, बाद में नहीं।",
        "gu": "હવામાનના પૂર્વાનુમાન પ્રમાણે ચાલો: ભીના/ઠંડા સમય પહેલાં પાક બચાવો, પછી નહીં.",
    },
    "s_tip_resource": {
        "en": "Prefer the organic action list and, if possible, add a soil sensor.",
        "hi": "जैविक उपायों को प्राथमिकता दें और हो सके तो मिट्टी सेंसर जोड़ें।",
        "gu": "જૈવિક ઉપાયોને પ્રાથમિકતા આપો અને શક્ય હોય તો માટી સેન્સર જોડો.",
    },
    "s_scale": {
        "en": "A >= 80 excellent | B >= 65 good | C >= 50 fair | D >= 35 poor | E < 35 critical",
        "hi": "A >= 80 उत्तम | B >= 65 अच्छा | C >= 50 ठीक-ठाक | D >= 35 कमज़ोर | E < 35 गंभीर",
        "gu": "A >= 80 ઉત્તમ | B >= 65 સારું | C >= 50 મધ્યમ | D >= 35 નબળું | E < 35 ગંભીર",
    },
    # ----------------------------------------------------------- crop advice --
    "c_advice": {
        "en": "{crop} is the best statistical match for these values. Confirm with your local "
              "KVK/agri officer before switching crops - the model uses only soil chemistry and "
              "climate, not market price or water availability.",
        "hi": "इन मानों के लिए {crop} सबसे उपयुक्त पाया गया। फसल बदलने से पहले स्थानीय KVK/कृषि "
              "अधिकारी से पुष्टि करें - मॉडल केवल मिट्टी और जलवायु देखता है, बाज़ार भाव या पानी की "
              "उपलब्धता नहीं।",
        "gu": "આ મૂલ્યો માટે {crop} સૌથી યોગ્ય મળ્યો. પાક બદલતા પહેલાં સ્થાનિક KVK/કૃષિ અધિકારી "
              "સાથે ખાતરી કરો - મોડેલ ફક્ત માટી અને હવામાન જુએ છે, બજારભાવ કે પાણીની ઉપલબ્ધતા નહીં.",
    },
    "c_envelope": {
        "en": "Matches the soil and climate envelope you entered.",
        "hi": "आपके दर्ज मिट्टी और जलवायु के दायरे से मेल खाता है।",
        "gu": "તમે દાખલ કરેલા માટી અને હવામાનના દાયરા સાથે મળે છે.",
    },
    "c_rules": {
        "en": "envelope-rules (model not trained yet)",
        "hi": "दायरा-नियम (मॉडल अभी प्रशिक्षित नहीं)",
        "gu": "દાયરા-નિયમ (મોડેલ હજી તાલીમબદ્ધ નથી)",
    },
    "c_band_high": {"en": "high", "hi": "उच्च", "gu": "ઊંચો"},
    "c_band_medium": {"en": "medium", "hi": "मध्यम", "gu": "મધ્યમ"},
    "c_band_low": {"en": "low", "hi": "कम", "gu": "નીચો"},
    "c_rice": {"en": "Needs standing water or assured irrigation; kharif staple for high-rainfall belts.",
               "hi": "खड़े पानी या पक्की सिंचाई चाहिए; ज़्यादा बारिश वाले इलाकों की खरीफ़ मुख्य फसल।",
               "gu": "ઊભું પાણી કે પાકી સિંચાઈ જોઈએ; વધુ વરસાદવાળા વિસ્તારોનો ખરીફ મુખ્ય પાક."},
    "c_maize": {"en": "Versatile kharif/rabi cereal; fits your rainfall window with 60-110 mm.",
                "hi": "खरीफ़/रबी दोनों में उपयुक्त अनाज; 60-110 मिमी बारिश वाले दायरे में ठीक बैठता है।",
                "gu": "ખરીફ/રવી બંનેમાં યોગ્ય અનાજ; 60-110 મિમી વરસાદવાળા દાયરામાં બંધ બેસે છે."},
    "c_wheat": {"en": "Rabi cereal; sow after the monsoon retreats.",
                "hi": "रबी अनाज; मानसून लौटने के बाद बोएँ।",
                "gu": "રવી અનાજ; ચોમાસું પાછું જાય પછી વાવો."},
    "c_pulse": {"en": "Rabi pulse that fixes nitrogen - good after a cereal.",
                "hi": "रबी दलहन जो नाइट्रोजन बनाती है - अनाज के बाद अच्छी है।",
                "gu": "રવી કઠોળ જે નાઇટ્રોજન બનાવે - અનાજ પછી સારી."},
    "c_cash": {"en": "Long-duration cash crop; needs 100+ kg/ha N and warm nights.",
                "hi": "लंबी अवधि की नक़दी फसल; 100+ किग्रा/हेक्टेयर नाइट्रोजन और गर्म रातें चाहिए।",
                "gu": "લાંબા સમયનો રોકડ પાક; 100+ કિગ્રા/હેક્ટર નાઇટ્રોજન અને ગરમ રાત્રિ જોઈએ."},
    "c_highk": {"en": "High K demand (200 kg/ha); best with drip + fertigation.",
                 "hi": "पोटैशियम की अधिक माँग (200 किग्रा/हेक्टेयर); ड्रिप + फर्टिगेशन के साथ सर्वोत्तम।",
                 "gu": "પોટેશિયમની વધુ જરૂર (200 કિગ્રા/હેક્ટર); ટપક + ખાતર-સિંચાઈ સાથે શ્રેષ્ઠ."},
    "c_heavy": {"en": "Heavy feeder; 80-120 kg/ha N with assured irrigation.",
                "hi": "पोषक तत्व खूब खाती है; पक्की सिंचाई के साथ 80-120 किग्रा/हेक्टेयर नाइट्रोजन।",
                "gu": "પોષકતત્વો ખૂબ જોઈએ; પાકી સિંચાઈ સાથે 80-120 કિગ્રા/હેક્ટર નાઇટ્રોજન."},
    "c_perennial": {"en": "Perennial; tolerates a wide pH band, needs a dry spell to flower.",
                    "hi": "बहुवर्षीय; pH का बड़ा दायरा सह लेती है, फूल के लिए सूखा दौर चाहिए।",
                    "gu": "બહુવર્ષીય; pH નો મોટો દાયરો સહે છે, ફૂલ માટે સૂકો સમય જોઈએ."},
    "c_shade": {"en": "Shade crop for 150-200 mm rainfall belts with mild temperatures.",
                "hi": "छाया वाली फसल, 150-200 मिमी बारिश और हल्के तापमान वाले इलाकों के लिए।",
                "gu": "છાયાનો પાક, 150-200 મિમી વરસાદ અને હળવા તાપમાનવાળા વિસ્તારો માટે."},
    "c_coastal": {"en": "Perennial for coastal humid belts (RH 90 %+).",
                  "hi": "तटीय नम इलाकों के लिए बहुवर्षीय (आर्द्रता 90%+)।",
                  "gu": "દરિયાકિનારાના ભેજવાળા વિસ્તારો માટે બહુવર્ષીય (ભેજ 90%+)."},
    # ------------------------------------------------------------- narrative --
    "n_healthy": {
        "en": "The leaf looks healthy ({crop}), confidence {conf}.",
        "hi": "पत्ती स्वस्थ दिख रही है ({crop}), भरोसा {conf}।",
        "gu": "પાન સ્વસ્થ દેખાય છે ({crop}), ભરોસો {conf}.",
    },
    "n_detected": {
        "en": "Detected {cond}{crop} with {conf} confidence - risk level {risk}.",
        "hi": "{cond}{crop} पाया गया, भरोसा {conf} - जोखिम स्तर {risk}।",
        "gu": "{cond}{crop} મળ્યું, ભરોસો {conf} - જોખમ સ્તર {risk}.",
    },
    "n_no_photo": {
        "en": "No leaf photo was supplied, so this analysis covers only the field conditions.",
        "hi": "पत्ती की फोटो नहीं दी गई, इसलिए यह विश्लेषण केवल खेत की स्थिति बताता है।",
        "gu": "પાનનો ફોટો આપ્યો નથી, તેથી આ વિશ્લેષણ ફક્ત ખેતરની સ્થિતિ બતાવે છે.",
    },
    "n_irrigation": {
        "en": "Irrigation: {action} - {reason}",
        "hi": "सिंचाई: {action} - {reason}",
        "gu": "સિંચાઈ: {action} - {reason}",
    },
    "n_weather": {
        "en": "Weather now: {cond}, {t}C, rain chance {rain}%.",
        "hi": "अभी मौसम: {cond}, {t}°C, बारिश की संभावना {rain}%।",
        "gu": "હાલ હવામાન: {cond}, {t}°C, વરસાદની સંભાવના {rain}%.",
    },
    "n_index": {
        "en": "Field health index {total}/100 (grade {grade}); weakest lever: {weakest}.",
        "hi": "खेत-स्वास्थ्य सूचकांक {total}/100 (ग्रेड {grade}); सबसे कमज़ोर पहलू: {weakest}।",
        "gu": "ખેત-આરોગ્ય સૂચકાંક {total}/100 (ગ્રેડ {grade}); સૌથી નબળું પાસું: {weakest}.",
    },
    "n_act_today": {
        "en": "Act today: start with the organic steps listed, and only escalate to the chemical "
              "option if the spread continues.",
        "hi": "आज ही कार्रवाई करें: पहले जैविक उपाय करें, रोग फैलने पर ही रासायनिक विकल्प अपनाएँ।",
        "gu": "આજે જ પગલું ભરો: પહેલાં જૈવિક ઉપાય કરો, રોગ ફેલાય તો જ રાસાયણિક વિકલ્પ લો.",
    },
    "n_see_reasons": {"en": "see reasons below", "hi": "कारण नीचे देखें", "gu": "કારણ નીચે જુઓ"},
    # --------------------------------------------------------------- sensors --
    "dev_north": {"en": "North field node", "hi": "उत्तरी खेत नोड", "gu": "ઉત્તર ખેતર નોડ"},
    "dev_south": {"en": "South field node", "hi": "दक्षिणी खेत नोड", "gu": "દક્ષિણ ખેતર નોડ"},
    "sim_note": {
        "en": "Simulated sensor stream (no physical ESP32 attached). The firmware contract is "
              "documented in modules/iot_sim.py; POST to /api/sensors/ingest to feed real data.",
        "hi": "सिम्युलेटेड सेंसर स्ट्रीम (कोई असली ESP32 नहीं जुड़ा है)। फ़र्मवेयर अनुबंध "
              "modules/iot_sim.py में है; असली डेटा के लिए /api/sensors/ingest पर POST करें।",
        "gu": "સિમ્યુલેટેડ સેન્સર સ્ટ્રીમ (કોઈ સાચું ESP32 જોડાયું નથી). ફર્મવેર કરાર "
              "modules/iot_sim.py માં છે; સાચો ડેટા માટે /api/sensors/ingest પર POST કરો.",
    },
    # ------------------------------------------- evaluation / metrics labels --
    # server-side display values that used to reach the UI as English slugs
    "p_immediate": {"en": "immediate", "hi": "तुरंत", "gu": "તરત"},
    "p_today": {"en": "today", "hi": "आज", "gu": "આજે"},
    "p_later": {"en": "later", "hi": "बाद में", "gu": "પછી"},
    "p_routine": {"en": "routine", "hi": "नियमित", "gu": "નિયમિત"},
    "k_organic": {"en": "organic", "hi": "जैविक", "gu": "જૈવિક"},
    "k_chemical": {"en": "chemical", "hi": "रासायनिक", "gu": "રાસાયણિક"},
    "k_prevention": {"en": "prevention", "hi": "रोकथाम", "gu": "અટકાવ"},
    "k_scout": {"en": "scouting", "hi": "निरीक्षण", "gu": "નિરીક્ષણ"},
    "band_high": {"en": "high", "hi": "उच्च", "gu": "ઊંચું"},
    "band_medium": {"en": "medium", "hi": "मध्यम", "gu": "મધ્યમ"},
    "band_low": {"en": "low", "hi": "निम्न", "gu": "નીચું"},
    "sev_low": {"en": "low", "hi": "कम", "gu": "ઓછી"},
    "sev_moderate": {"en": "moderate", "hi": "मध्यम", "gu": "મધ્યમ"},
    "sev_high": {"en": "high", "hi": "उच्च", "gu": "ઊંચી"},
    "sev_critical": {"en": "critical", "hi": "गंभीर", "gu": "ગંભીર"},
    "adv_none": {"en": "none", "hi": "कुछ नहीं", "gu": "કંઈ નહીં"},
    "adv_observe": {"en": "observe", "hi": "निगरानी रखें", "gu": "નજર રાખો"},
    "adv_soon": {"en": "act soon", "hi": "जल्दी करें", "gu": "જલદી કરો"},
    "adv_now": {"en": "act now", "hi": "अभी करें", "gu": "તરત કરો"},
    "adv_emergency": {"en": "emergency", "hi": "आपातकाल", "gu": "આપાતકાલ"},
    "stress_dry": {"en": "dry", "hi": "सूखा", "gu": "સૂકું"},
    "stress_wet": {"en": "waterlogged", "hi": "जलभराव", "gu": "પાણી ભરાયેલું"},
    "stress_ok": {"en": "adequate", "hi": "पर्याप्त", "gu": "પૂરતું"},
    "sub_water": {"en": "water", "hi": "पानी", "gu": "પાણી"},
    "sub_weather": {"en": "weather", "hi": "मौसम", "gu": "હવામાન"},
    "sub_disease": {"en": "disease", "hi": "रोग", "gu": "રોગ"},
    "sub_resource": {"en": "resource", "hi": "संसाधन", "gu": "સાધનો"},
    "trend_rising": {"en": "rising", "hi": "बढ़ रहा है", "gu": "વધી રહ્યો છે"},
    "trend_falling": {"en": "falling", "hi": "घट रहा है", "gu": "ઘટી રહ્યો છે"},
    "trend_drying": {"en": "drying", "hi": "सूख रहा है", "gu": "સૂકાઈ રહ્યો છે"},
    "trend_wetting": {"en": "wetting", "hi": "गीला हो रहा है", "gu": "ભીનું થાય છે"},
    "trend_stable": {"en": "stable", "hi": "स्थिर", "gu": "સ્થિર"},
    "st_healthy": {"en": "healthy", "hi": "स्वस्थ", "gu": "સ્વસ્થ"},
    "st_battery_low": {"en": "battery low", "hi": "बैटरी कम", "gu": "બેટરી ઓછી"},
    "st_charge_now": {"en": "charge now", "hi": "अभी चार्ज करें", "gu": "હમણાં ચાર્જ કરો"},
    "s_tip_disease": {
        "en": "Scout and treat the detected condition early; a healthy canopy lifts every sub-score.",
        "hi": "पहचाने गए रोग की जल्दी निगरानी करें और इलाज करें; स्वस्थ पत्तियाँ हर स्कोर बढ़ाती हैं।",
        "gu": "ઓળખાયેલા રોગની વહેલી નજર રાખો અને ઉપાય કરો; સ્વસ્થ પાન દરેક સ્કોર વધારે છે.",
    },
    "md_field_note": {
        "en": "Macro-F1 over classes present in the held-out PlantDoc field split; absent "
              "classes are reported in classes_absent.",
        "hi": "PlantDoc के अलग रखे गए खेत-स्प्लिट में मौजूद वर्गों पर मैक्रो-F1; न मिले वर्ग "
              "classes_absent में बताए गए हैं।",
        "gu": "PlantDoc ના અલગ રાખેલા ખેતર-સ્પ્લિટમાં હાજર વર્ગો પર મેક્રો-F1; ન મળેલા વર્ગ "
              "classes_absent માં દર્શાવ્યા છે.",
    },
    "md_centercrop": {"en": "center-crop, single view (training-time eval transform)",
                      "hi": "सेंटर-क्रॉप, एक दृश्य (प्रशिक्षण-काल का ट्रांसफ़ॉर्म)",
                      "gu": "સેન્ટર-ક્રોપ, એક દૃશ્ય (તાલીમ સમયનું ટ્રાન્સફોર્મ)"},
    "md_centercrop_tta": {"en": "center-crop + mirror TTA", "hi": "सेंटर-क्रॉप + मिरर TTA",
                          "gu": "સેન્ટર-ક્રોપ + મિરર TTA"},
    "md_leafcrop": {"en": "leaf-region crop (largest green blob), single view",
                    "hi": "पत्ती-क्षेत्र क्रॉप (सबसे बड़ा हरा हिस्सा), एक दृश्य",
                    "gu": "પાન-વિસ્તાર ક્રોપ (સૌથી મોટો લીલો ભાગ), એક દૃશ્ય"},
    "md_ensemble": {"en": "center-crop + leaf-crop softmax average",
                    "hi": "सेंटर-क्रॉप + पत्ती-क्रॉप सॉफ़्टमैक्स औसत",
                    "gu": "સેન્ટર-ક્રોપ + પાન-ક્રોપ સોફ્ટમેક્સ સરેરાશ"},
    "md_ensemble_tta": {"en": "center-crop + leaf-crop, mirror TTA on both",
                        "hi": "सेंटर-क्रॉप + पत्ती-क्रॉप, दोनों पर मिरर TTA",
                        "gu": "સેન્ટર-ક્રોપ + પાન-ક્રોપ, બંને પર મિરર TTA"},
}


def say(key: str, lang: str | None = None, **fmt: Any) -> str:
    """Render a row; unknown keys come back as the key, formatting errors never raise."""
    row = PHRASES.get(key)
    if not row:
        return key
    tag = (lang or "en")[:2].lower()
    if tag not in LANGS:
        tag = "en"
    text = row.get(tag) or row["en"]
    try:
        return text.format(**fmt) if fmt else text
    except (KeyError, IndexError):
        return text


def checks() -> list[str]:
    """Rows missing a language (empty == fully localised)."""
    return sorted(f"{k}:{lang}" for k, row in PHRASES.items()
                  for lang in LANGS if not row.get(lang))


def wcode_label(code: Any, lang: str | None = None, english: str | None = None) -> str:
    """WMO code -> localized weather word, falling back to the English label."""
    try:
        key = f"wcode_{int(code)}"
    except (TypeError, ValueError):
        return english or ""
    if key in PHRASES:
        return say(key, lang)
    return english or ""
