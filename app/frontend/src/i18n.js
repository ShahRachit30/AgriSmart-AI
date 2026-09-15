// Frontend strings (EN / HI / GU). Mirrors modules/i18n.py so the API and the UI
// speak the same language. Missing keys fall back to English.

export const LANGS = ['en', 'hi', 'gu']

const STRINGS = {
  app_name: { en: 'AgriSmart AI', hi: 'एग्रीस्मार्ट AI', gu: 'એગ્રીસ્માર્ટ AI' },
  tagline: {
    en: 'Intelligent agriculture for a sustainable future',
    hi: 'सतत कृषि के लिए बुद्धिमान तकनीक',
    gu: 'ટકાઉ ખેતી માટે બુદ્ધિશાળી તકનીક',
  },
  dashboard: { en: 'Dashboard', hi: 'डैशबोर्ड', gu: 'ડેશબોર્ડ' },
  results: { en: 'Results', hi: 'परिणाम', gu: 'પરિણામ' },
  upload_title: { en: 'Leaf photo', hi: 'पत्ती की फोटो', gu: 'પાનનો ફોટો' },
  upload_hint: {
    en: 'Take the photo in daylight, fill the frame with one leaf.',
    hi: 'दिन की रोशनी में फोटो लें, एक ही पत्ती फ्रेम में रखें।',
    gu: 'દિવસના અજવાળામાં ફોટો લો, એક જ પાન ફ્રેમમાં રાખો.',
  },
  choose_photo: { en: 'Choose photo', hi: 'फोटो चुनें', gu: 'ફોટો પસંદ કરો' },
  field_title: { en: 'Field conditions', hi: 'खेत की स्थिति', gu: 'ખેતરની સ્થિતિ' },
  soil_moisture: { en: 'Soil moisture (%)', hi: 'मिट्टी की नमी (%)', gu: 'જમીનનો ભેજ (%)' },
  soil_ph: { en: 'Soil pH', hi: 'मिट्टी pH', gu: 'જમીન pH' },
  city: { en: 'City (live weather)', hi: 'शहर (लाइव मौसम)', gu: 'શહેર (લાઇવ હવામાન)' },
  planted_crop: { en: 'Planted crop', hi: 'बोई गई फसल', gu: 'વાવેલો પાક' },
  area: { en: 'Area (hectare)', hi: 'क्षेत्र (हेक्टेयर)', gu: 'ક્ષેત્ર (હેક્ટર)' },
  analyze: { en: 'Analyze', hi: 'विश्लेषण करें', gu: 'વિશ્લેષણ કરો' },
  analyzing: { en: 'Analyzing…', hi: 'विश्लेषण हो रहा है…', gu: 'વિશ્લેષણ થઈ રહ્યું છે…' },
  prediction: { en: 'Detection', hi: 'पहचान', gu: 'ઓળખ' },
  confidence: { en: 'Confidence', hi: 'भरोसा', gu: 'ભરોસો' },
  risk: { en: 'Risk', hi: 'जोखिम', gu: 'જોખમ' },
  actions: { en: 'What to do', hi: 'क्या करें', gu: 'શું કરવું' },
  irrigation: { en: 'Irrigation', hi: 'सिंचाई', gu: 'સિંચાઈ' },
  weather: { en: 'Weather', hi: 'मौसम', gu: 'હવામાન' },
  sustainability: { en: 'Sustainability', hi: 'टिकाऊपन', gu: 'ટકાઉપણું' },
  assistant: { en: 'Farmer assistant', hi: 'किसान सहायक', gu: 'ખેડૂત સહાયક' },
  sensors: { en: 'Field sensors (simulated)', hi: 'खेत सेंसर (सिम्युलेटेड)', gu: 'ખેતર સેન્સર (સિમ્યુલેટેડ)' },
  crop_advisory: { en: 'Crop recommendation', hi: 'फसल सुझाव', gu: 'પાક સૂચન' },
  ask_placeholder: {
    en: 'Ask about the disease, treatment, water, weather or crops…',
    hi: 'रोग, उपचार, पानी, मौसम या फसल के बारे में पूछें…',
    gu: 'રોગ, સારવાર, પાણી, હવામાન કે પાક વિશે પૂછો…',
  },
  send: { en: 'Send', hi: 'भेजें', gu: 'મોકલો' },
  source: { en: 'Sources', hi: 'स्रोत', gu: 'સ્રોત' },
  no_analysis: {
    en: 'Upload a leaf photo and press Analyze to see the full advisory.',
    hi: 'पूरी सलाह देखने के लिए पत्ती की फोटो अपलोड करें और विश्लेषण दबाएँ।',
    gu: 'પૂરી સલાહ જોવા માટે પાનનો ફોટો અપલોડ કરો અને વિશ્લેષણ દબાવો.',
  },
  new_analysis: { en: 'New analysis', hi: 'नया विश्लेषण', gu: 'નવું વિશ્લેષણ' },
  try_sample: {
    en: 'No photo handy? Tap a verified sample field photo',
    hi: 'फोटो नहीं है? कोई प्रमाणित नमूना फोटो चुनें',
    gu: 'ફોટો નથી? ચકાસાયેલો નમૂનો પસંદ કરો',
  },
  sample_right: { en: 'correct', hi: 'सही', gu: 'સાચું' },
  upload_preparing: {
    en: 'Preparing photo…', hi: 'फोटो तैयार हो रही है…', gu: 'ફોટો તૈયાર થાય છે…',
  },
  upload_compressed: {
    en: 'Photo resized for upload', hi: 'अपलोड के लिए फोटो छोटी की गई',
    gu: 'અપલોડ માટે ફોટો નાનો કર્યો',
  },
  upload_sending: {
    en: 'uploading the photo and running the analysis…',
    hi: 'फोटो अपलोड हो रही है और विश्लेषण चल रहा है…',
    gu: 'ફોટો અપલોડ થાય છે અને વિશ્લેષણ ચાલે છે…',
  },
  change_photo: {
    en: 'Choose a different photo', hi: 'दूसरी फोटो चुनें', gu: 'બીજો ફોટો પસંદ કરો',
  },
  preview_unavailable: {
    en: 'Preview not available in this browser (HEIC) - the server will still read it',
    hi: 'इस ब्राउज़र में प्रीव्यू उपलब्ध नहीं (HEIC) - सर्वर इसे पढ़ लेगा',
    gu: 'આ બ્રાઉઝરમાં પ્રીવ્યૂ ઉપલબ્ધ નથી (HEIC) - સર્વર તેને વાંચી લેશે',
  },
  err_picker: {
    en: 'Could not open the file picker. Please drag & drop the photo onto the box instead.',
    hi: 'फ़ाइल चयनकर्ता नहीं खुल सका। कृपया फोटो को बॉक्स में खींचकर छोड़ें।',
    gu: 'ફાઇલ પિકર ખૂલી શક્યું નથી. કૃપા કરીને ફોટો બોક્સમાં ખેંચીને મૂકો.',
  },
  analyze_photo: { en: 'Analyze this photo', hi: 'इस फोटो का विश्लेषण करें', gu: 'આ ફોટોનું વિશ્લેષણ કરો' },
  photo_ready: {
    en: 'photo ready - press to run the full analysis',
    hi: 'फोटो तैयार - पूरा विश्लेषण चलाने के लिए दबाएँ',
    gu: 'ફોટો તૈયાર - પૂરું વિશ્લેષણ ચલાવવા દબાવો',
  },
  remove: { en: 'Remove', hi: 'हटाएँ', gu: 'દૂર કરો' },
  or_drag: { en: 'or drag & drop it here', hi: 'या यहाँ खींचकर छोड़ें', gu: 'અથવા અહીં ખેંચીને મૂકો' },
  accepted_types: { en: 'JPG, PNG, WebP, BMP, TIFF, HEIC', hi: 'JPG, PNG, WebP, BMP, TIFF, HEIC',
    gu: 'JPG, PNG, WebP, BMP, TIFF, HEIC' },
  err_heic: {
    en: 'iPhone HEIC photos are not supported yet - set the camera to "Most Compatible", or export/share the photo as JPEG and try again.',
    hi: 'iPhone की HEIC फोटो अभी समर्थित नहीं है - कैमरा "Most Compatible" पर रखें, या फोटो को JPEG में निर्यात करके फिर कोशिश करें।',
    gu: 'iPhone ના HEIC ફોટા હજી સપોર્ટેડ નથી - કૅમેરા "Most Compatible" રાખો, અથવા ફોટો JPEG માં એક્સપોર્ટ કરીને ફરી પ્રયાસ કરો.',
  },
  err_type: {
    en: 'That file is not an image the app can read. Please choose a JPG, PNG or WebP file.',
    hi: 'यह फ़ाइल पढ़ने योग्य छवि नहीं है। कृपया JPG, PNG या WebP चुनें।',
    gu: 'આ ફાઇલ વાંચી શકાય તેવી છબી નથી. કૃપા કરીને JPG, PNG કે WebP પસંદ કરો.',
  },
  err_size: {
    en: 'That photo is larger than the limit - please compress it or pick a smaller one.',
    hi: 'यह फोटो सीमा से बड़ी है - कृपया इसे छोटा करें या कोई छोटी फोटो चुनें।',
    gu: 'આ ફોટો મર્યાદા કરતાં મોટો છે - કૃપા કરીને તેને નાનો કરો કે બીજો ફોટો પસંદ કરો.',
  },
  sample_hard: { en: 'hard case', hi: 'कठिन केस', gu: 'કઠિન કેસ' },
  metrics: { en: 'Held-out field metrics', hi: 'फील्ड टेस्ट मेट्रिक्स', gu: 'ફીલ્ડ ટેસ્ટ મેટ્રિક્સ' },
  live: { en: 'LIVE', hi: 'लाइव', gu: 'લાઇવ' },
  offline: { en: 'offline', hi: 'ऑफलाइन', gu: 'ઑફલાઇન' },
  grade: { en: 'Grade', hi: 'ग्रेड', gu: 'ગ્રેડ' },
  weakest: { en: 'Weakest lever', hi: 'सबसे कमजोर पहलू', gu: 'સૌથી નબળું પાસું' },
  reasons: { en: 'Reasons', hi: 'कारण', gu: 'કારણો' },
  top3: { en: 'Top 3', hi: 'शीर्ष 3', gu: 'ટોચના 3' },
  demo_mode: {
    en: 'Model not trained yet - the advisory modules still work.',
    hi: 'मॉडल अभी प्रशिक्षित नहीं - सलाह मॉड्यूल फिर भी काम करते हैं।',
    gu: 'મોડેલ હજી તાલીમ નથી - સલાહ મોડ્યુલ હજી કામ કરે છે.',
  },

  // ---- strings that used to be hardcoded in App.jsx (whole-UI language switch) --
  footer_note: {
    en: 'Advisory only — confirm with your local agriculture officer.',
    hi: 'केवल सलाह — अपने स्थानीय कृषि अधिकारी से पुष्टि करें।',
    gu: 'ફક્ત સલાહ — તમારા સ્થાનિક કૃષિ અધિકારી સાથે ખાતરી કરો.',
  },
  model_ready: { en: 'model {m} ready', hi: 'मॉडल {m} तैयार', gu: 'મોડેલ {m} તૈયાર' },
  alt_selected: { en: 'selected leaf', hi: 'चुनी हुई पत्ती', gu: 'પસંદ કરેલું પાન' },
  alt_analyzed: { en: 'analysed leaf', hi: 'विश्लेषित पत्ती', gu: 'વિશ્લેષિત પાન' },
  alt_sample: { en: 'sample leaf photo', hi: 'नमूना पत्ती की फोटो', gu: 'નમૂના પાનનો ફોટો' },
  expected: { en: 'expected', hi: 'अपेक्षित', gu: 'અપેક્ષિત' },
  sim_badge: { en: 'SIMULATED', hi: 'सिम्युलेटेड', gu: 'સિમ્યુલેટેડ' },
  node: { en: 'node', hi: 'नोड', gu: 'નોડ' },
  mf1: { en: 'macro-F1 (primary)', hi: 'मैक्रो-F1 (मुख्य)', gu: 'મેક્રો-F1 (મુખ્ય)' },
  accuracy: { en: 'accuracy', hi: 'सटीकता', gu: 'ચોકસાઈ' },
  top3_acc: { en: 'top-3 accuracy', hi: 'टॉप-3 सटीकता', gu: 'ટોપ-3 ચોકસાઈ' },
  images_field: { en: 'images (PlantDoc field)', hi: 'तस्वीरें (PlantDoc फील्ड)', gu: 'છબીઓ (PlantDoc ફીલ્ડ)' },
  classes_scored: { en: 'classes scored', hi: 'स्कोर किए वर्ग', gu: 'સ્કોર થયેલા વર્ગ' },
  metrics_note: {
    en: 'Held-out field photos (never trained on). Absent classes are listed in report/metrics.json.',
    hi: 'अलग रखी गई फील्ड तस्वीरें (इन पर प्रशिक्षण नहीं हुआ)। न मिले वर्ग report/metrics.json में हैं।',
    gu: 'અલગ રાખેલા ખેતરના ફોટા (આના પર તાલીમ થઈ નથી). ન મળેલા વર્ગ report/metrics.json માં છે.',
  },
  metrics_after: {
    en: 'Metrics appear after python model/evaluate.py.',
    hi: 'मेट्रिक्स python model/evaluate.py के बाद दिखते हैं।',
    gu: 'મેટ્રિક્સ python model/evaluate.py પછી દેખાય છે.',
  },
  no_photo_note: {
    en: 'No photo was analysed — the advisory below uses only the field data.',
    hi: 'कोई फोटो विश्लेषित नहीं हुई — नीचे की सलाह केवल खेत के आँकड़ों पर है।',
    gu: 'કોઈ ફોટો વિશ્લેષણ થયો નથી — નીચેની સલાહ ફક્ત ખેતરના આંકડા પર છે.',
  },
  condition: { en: 'condition', hi: 'रोग/स्थिति', gu: 'સ્થિતિ' },
  confidence_band: { en: 'confidence band', hi: 'भरोसे का स्तर', gu: 'ભરોસાનું સ્તર' },
  advisory_level: { en: 'advisory level', hi: 'सलाह का स्तर', gu: 'સલાહનું સ્તર' },
  kb_severity: { en: 'KB severity', hi: 'KB गंभीरता', gu: 'KB ગંભીરતા' },
  what_to_look_for: { en: 'what to look for', hi: 'क्या देखें', gu: 'શું જોવું' },
  chemical_option: {
    en: 'Chemical escalation option (only if needed)',
    hi: 'रासायनिक उपाय (ज़रूरत पड़ने पर ही)',
    gu: 'રાસાયણિક ઉપાય (જરૂર પડે તો જ)',
  },
  soil_moisture_short: { en: 'soil moisture', hi: 'मिट्टी की नमी', gu: 'માટીનો ભેજ' },
  rain_probability: { en: 'rain probability', hi: 'बारिश की संभावना', gu: 'વરસાદની સંભાવના' },
  water_stress: { en: 'water stress', hi: 'पानी का तनाव', gu: 'પાણીનો તણાવ' },
  humidity: { en: 'humidity', hi: 'आर्द्रता', gu: 'ભેજ' },
  wind: { en: 'wind', hi: 'हवा', gu: 'પવન' },
  rain_today_week: { en: 'rain today / week', hi: 'आज / सप्ताह की बारिश', gu: 'આજે / અઠવાડિયાનો વરસાદ' },
  why: { en: 'why', hi: 'क्यों', gu: 'કેમ' },
  engine: { en: 'engine', hi: 'इंजन', gu: 'એન્જિન' },
  temperature: { en: 'temperature', hi: 'तापमान', gu: 'તાપમાન' },
  battery_signal: { en: 'battery / signal', hi: 'बैटरी / सिग्नल', gu: 'બેટરી / સિગ્નલ' },
  next_sample: { en: 'next sample', hi: 'अगला नमूना', gu: 'આગળનો નમૂનો' },
  trend_soil_2h: {
    en: 'soil moisture, last 2 h', hi: 'मिट्टी की नमी, पिछले 2 घंटे', gu: 'માટીનો ભેજ, છેલ્લા 2 કલાક',
  },
  air_temperature: { en: 'air temperature', hi: 'हवा का तापमान', gu: 'હવાનું તાપમાન' },
  use_soil_card: { en: 'use sample soil card', hi: 'नमूना मिट्टी कार्ड भरें', gu: 'નમૂના માટી કાર્ડ વાપરો' },
  use_sensor_moisture: {
    en: 'use sensor soil moisture', hi: 'सेंसर से मिट्टी की नमी लें', gu: 'સેન્સરથી માટીનો ભેજ લો',
  },
  crop_inputs_suffix: {
    en: 'inputs (N-P-K + climate)', hi: 'इनपुट (N-P-K + जलवायु)', gu: 'ઇનપુટ (N-P-K + હવામાન)',
  },
  weather_unavailable: {
    en: 'Live weather unavailable — manual values were used.',
    hi: 'लाइव मौसम उपलब्ध नहीं — मैनुअल मान उपयोग हुए।',
    gu: 'લાઇવ હવામાન ઉપલબ્ધ નથી — મેન્યુઅલ મૂલ્યો વપરાયા.',
  },
  chat_intro: {
    en: 'Ask anything about the analysis. Answers use only the numbers on this screen — nothing is invented.',
    hi: 'विश्लेषण के बारे में कुछ भी पूछें। उत्तर केवल इस स्क्रीन के आँकड़ों से बनते हैं — कुछ भी मनगढ़ंत नहीं।',
    gu: 'વિશ્લેષણ વિશે કંઈ પણ પૂછો. જવાબ ફક્ત આ સ્ક્રીનના આંકડામાંથી બને છે — કંઈ પણ ઉપજાવેલું નથી.',
  },
  chip_disease: { en: 'What disease is this?', hi: 'यह कौन-सा रोग है?', gu: 'આ કયો રોગ છે?' },
  chip_irrigate: { en: 'Should I irrigate today?', hi: 'क्या आज सिंचाई करूँ?', gu: 'આજે સિંચાઈ કરવી?' },
  chip_rain: { en: 'Will it rain?', hi: 'क्या बारिश होगी?', gu: 'વરસાદ થશે?' },
  chip_crop: { en: 'Which crop should I plant next?', hi: 'आगे कौन-सी फसल बोऊँ?', gu: 'આગળ કયો પાક વાવું?' },
  chip_prevent: { en: 'How do I prevent this?', hi: 'इसकी रोकथाम कैसे करें?', gu: 'આની અટકાવ કેમ કરવી?' },
  switch_note: {
    en: 'Switching language re-renders this page and reloads the analysis in the new language.',
    hi: 'भाषा बदलने पर यह पूरा पेज और विश्लेषण नई भाषा में फिर से बनता है।',
    gu: 'ભાષા બદલવાથી આ આખું પાનું અને વિશ્લેષણ નવી ભાષામાં ફરી બને છે.',
  },
  crop_tomato: { en: 'tomato', hi: 'टमाटर', gu: 'ટામેટું' },
  crop_potato: { en: 'potato', hi: 'आलू', gu: 'બટાકું' },
  crop_corn: { en: 'corn', hi: 'मक्का', gu: 'મકાઈ' },
  crop_apple: { en: 'apple', hi: 'सेब', gu: 'સેબ' },
  crop_grape: { en: 'grape', hi: 'अंगूर', gu: 'દ્રાક્ષ' },
  crop_bell_pepper: { en: 'bell pepper', hi: 'शिमला मिर्च', gu: 'શિમલા મરચું' },
  soil_ph_short: { en: 'soil pH', hi: 'मिट्टी pH', gu: 'જમીન pH' },
  dev_north_option: { en: 'esp32-field-1 · north field (tomato)', hi: 'esp32-field-1 · उत्तरी खेत (टमाटर)', gu: 'esp32-field-1 · ઉત્તર ખેતર (ટામેટું)' },
  dev_south_option: { en: 'esp32-field-2 · south field (potato)', hi: 'esp32-field-2 · दक्षिणी खेत (आलू)', gu: 'esp32-field-2 · દક્ષિણ ખેતર (બટાકું)' },
  dev_poly_option: { en: 'esp32-greenhouse · polyhouse (pepper)', hi: 'esp32-greenhouse · पॉलीहाउस (मिर्च)', gu: 'esp32-greenhouse · પોલિહાઉસ (મરચું)' },
  relocalizing: {
    en: 'Re-rendering in the new language…', hi: 'नई भाषा में फिर से बना रहे हैं…', gu: 'નવી ભાષામાં ફરી બનાવી રહ્યા છીએ…',
  },
  et0_proxy: { en: 'ET₀ proxy', hi: 'ET₀ अनुमान', gu: 'ET₀ અંદાજ' },
  footer_core: {
    en: 'core = ResNet18 crop-disease classifier (PlantVillage → PlantDoc field test) · bonuses: irrigation (B), weather (C), sustainability (D), assistant (E), crop recommendation (A), IoT (F)',
    hi: 'मुख्य = ResNet18 फसल-रोग क्लासिफ़ायर (PlantVillage → PlantDoc फील्ड टेस्ट) · बोनस: सिंचाई (B), मौसम (C), टिकाऊपन (D), सहायक (E), फसल सुझाव (A), IoT (F)',
    gu: 'મુખ્ય = ResNet18 પાક-રોગ ક્લાસિફાયર (PlantVillage → PlantDoc ફીલ્ડ ટેસ્ટ) · બોનસ: સિંચાઈ (B), હવામાન (C), ટકાઉપણું (D), સહાયક (E), પાક સૂચન (A), IoT (F)',
  },
  donut_aria: {
    en: 'sustainability score {v} of 100', hi: 'टिकाऊपन स्कोर 100 में से {v}', gu: 'ટકાઉપણું સ્કોર 100 માંથી {v}',
  },
  trend_aria: { en: 'trend', hi: 'रुझान', gu: 'વલણ' },
  status: { en: 'status', hi: 'स्थिति', gu: 'સ્થિતિ' },
  badge_grounded: { en: 'grounded', hi: 'प्रमाणित', gu: 'પ્રમાણિત' },
  badge_llm: { en: 'grounded + {p}', hi: 'प्रमाणित + {p}', gu: 'પ્રમાણિત + {p}' },
  engine_tip_grounded: {
    en: 'Answers are built only from the numbers on this screen (deterministic engine, works offline).',
    hi: 'उत्तर केवल इस स्क्रीन के आँकड़ों से बनते हैं (नियत इंजन, ऑफ़लाइन भी चलता है)।',
    gu: 'જવાબ ફક્ત આ સ્ક્રીનના આંકડામાંથી બને છે (નિશ્ચિત એન્જિન, ઑફલાઇન પણ ચાલે છે).',
  },
  engine_tip_llm: {
    en: 'Grounded answers, phrased by the {p} LLM. Switch it off with allow_llm=false.',
    hi: 'प्रमाणित उत्तर, {p} LLM द्वारा लिखे गए। allow_llm=false से बंद करें।',
    gu: 'પ્રમાણિત જવાબ, {p} LLM દ્વારા લખાયેલા. allow_llm=false થી બંધ કરો.',
  },

  // ---- decluttering pass: progressive disclosure + at-a-glance summary ---------
  details: { en: 'Details', hi: 'विवरण', gu: 'વિગતો' },
  at_a_glance: { en: 'At a glance', hi: 'एक नज़र में', gu: 'એક નજરમાં' },
  optional: { en: 'optional', hi: 'वैकल्पिक', gu: 'વૈકલ્પિક' },
  start_analysis: { en: 'Start an analysis', hi: 'विश्लेषण शुरू करें', gu: 'વિશ્લેષણ શરૂ કરો' },
  inference_time: { en: 'inference time', hi: 'अनुमान समय', gu: 'અનુમાન સમય' },
  forecast_4day: { en: '4-day forecast', hi: '4 दिन का पूर्वानुमान', gu: '4 દિવસની આગાહી' },
  subscore_breakdown: {
    en: 'score breakdown (water · weather · disease · resource)',
    hi: 'स्कोर विवरण (पानी · मौसम · रोग · संसाधन)',
    gu: 'સ્કોર વિગત (પાણી · હવામાન · રોગ · સંસાધન)',
  },
  findings: { en: 'findings', hi: 'निष्कर्ष', gu: 'તારણો' },
}

export function makeT(lang) {
  return (key, vars) => {
    let text = (STRINGS[key] && (STRINGS[key][lang] || STRINGS[key].en)) || key
    if (vars) {
      Object.entries(vars).forEach(([k, v]) => { text = text.replaceAll(`{${k}}`, String(v)) })
    }
    return text
  }
}

export const LANG_LABEL = { en: 'EN', hi: 'हि', gu: 'ગુ' }
