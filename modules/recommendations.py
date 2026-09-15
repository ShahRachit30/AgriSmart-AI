"""Knowledge base + risk engine for the 18 AgriSmart classes.

For every class we publish: crop, condition, severity, typical symptoms, an
organic-first action list, a chemical option (with dose + safety note), and
prevention. All text is advisory and cites the ICAR/extension-style practice it
follows; the API always appends the disclaimer from `modules/i18n.py`.

Risk decision table (deterministic, see docs/architecture.md)
------------------------------------------------------------
healthy                                     -> low
disease, confidence >= KB_SEVERITY_CONF     -> KB severity
disease, LOW_CONF <= c < KB_SEVERITY_CONF   -> moderate + "verify before spraying"
disease, confidence < LOW_CONF              -> moderate + "re-photograph"
humid/wet weather context                   -> upgrade one step (max critical)
severity is never escalated past "critical".
"""
from __future__ import annotations

from typing import Any

from .app_phrases import say
from .i18n import normalise, t
from . import kb_i18n
from .assistant_i18n import localize_condition

KB_SEVERITY_CONF = 0.75
LOW_CONF = 0.50
RISK_ORDER = ["low", "moderate", "high", "critical"]

CROPS = {
    "apple": {"en": "Apple", "hi": "सेब", "gu": "સેબ"},
    "bell_pepper": {"en": "Bell pepper", "hi": "शिमला मिर्च", "gu": "શિમલા મરચું"},
    "blueberry": {"en": "Blueberry", "hi": "ब्लूबेरी", "gu": "બ્લૂબેરી"},
    "cherry": {"en": "Cherry", "hi": "चेरी", "gu": "ચેરી"},
    "corn": {"en": "Corn (maize)", "hi": "मक्का", "gu": "મકાઈ"},
    "grape": {"en": "Grape", "hi": "अंगूर", "gu": "દ્રાક્ષ"},
    "orange": {"en": "Orange (citrus)", "hi": "संतरा", "gu": "નારંગી"},
    "peach": {"en": "Peach", "hi": "आड़ू", "gu": "આલૂ"},
    "potato": {"en": "Potato", "hi": "आलू", "gu": "બટાકા"},
    "raspberry": {"en": "Raspberry", "hi": "रास्पबेरी", "gu": "રાસ્પબેરી"},
    "soybean": {"en": "Soybean", "hi": "सोयाबीन", "gu": "સોયાબીન"},
    "squash": {"en": "Squash / pumpkin", "hi": "कद्दू वर्ग", "gu": "કોળું વર્ગ"},
    "strawberry": {"en": "Strawberry", "hi": "स्ट्रॉबेरी", "gu": "સ્ટ્રોબેરી"},
    "tomato": {"en": "Tomato", "hi": "टमाटर", "gu": "ટામેટું"},
}

# slug -> knowledge base entry
KB: dict[str, dict[str, Any]] = {
    "apple_scab": {
        "crop": "apple", "condition": "Apple scab (Venturia inaequalis)", "severity": "high",
        "symptoms": ["Olive-green to black velvety spots on leaves and fruit",
                     "Leaves curl, yellow and drop early"],
        "organic": ["Rake and destroy fallen leaves - the fungus overwinters in leaf litter",
                    "Prune to open the canopy so leaves dry faster",
                    "Spray 5 % neem oil or a Bordeaux mixture (1 %) at green-tip and again after petal fall"],
        "chemical": {"product": "Captan 50 % WP or Dodine 65 % WP",
                     "dose": "2 g/L water, 2-3 sprays 10-14 days apart",
                     "note": "Respect the pre-harvest interval on the label"},
        "prevention": ["Plant scab-resistant cultivars", "Avoid overhead irrigation in spring"],
    },
    "apple_black_rot": {
        "crop": "apple", "condition": "Apple black rot (Botryosphaeria obtusa)", "severity": "high",
        "symptoms": ["Purple leaf spots that enlarge into 'frog-eye' lesions",
                     "Fruit rots from the calyx end, shrivelling into black mummies"],
        "organic": ["Remove cankers and mummified fruit during winter pruning",
                    "Disinfect pruning tools with 70 % alcohol between trees",
                    "Apply copper oxychloride 0.3 % at bud break"],
        "chemical": {"product": "Myclobutanil 10 % WP or Thiophanate-methyl 70 % WP",
                     "dose": "1 g/L, sprays at 10-14 day intervals in the wet season",
                     "note": "Rotate actives to avoid resistance"},
        "prevention": ["Keep trees vigorous but avoid excess nitrogen",
                       "Control fruit fly and bird damage that open entry wounds"],
    },
    "apple_healthy": {
        "crop": "apple", "condition": "Healthy apple leaf", "severity": "low",
        "symptoms": ["Uniform green leaf, no lesions"], "organic": [], "chemical": None,
        "prevention": ["Continue the standard scab-prevention calendar",
                       "Scout weekly, especially after rain"],
    },
    "pepper_bacterial_spot": {
        "crop": "bell_pepper", "condition": "Bell pepper bacterial spot (Xanthomonas)", "severity": "high",
        "symptoms": ["Water-soaked spots turning brown with yellow halos",
                     "Severe leaf drop exposes fruit to sunscald"],
        "organic": ["Remove and burn infected debris - do not compost",
                    "Spray copper hydroxide 0.2 % + bio-agent Bacillus subtilis",
                    "Avoid working in the field while foliage is wet"],
        "chemical": {"product": "Copper oxychloride 50 % WP (+ Streptocycline 100 ppm)",
                     "dose": "3 g/L copper, 7-10 day interval, max 4 sprays",
                     "note": "Bactericides are protective - cover new growth"},
        "prevention": ["Use certified disease-free seed and rotate away from peppers/tomatoes 2 years",
                       "Drip irrigate instead of overhead"],
    },
    "pepper_healthy": {
        "crop": "bell_pepper", "condition": "Healthy bell pepper leaf", "severity": "low",
        "symptoms": ["Glossy green leaf, no spotting"], "organic": [], "chemical": None,
        "prevention": ["Mulch to stop splash-dispersal of bacteria", "Stake plants for airflow"],
    },
    "corn_grey_leaf_spot": {
        "crop": "corn", "condition": "Corn grey leaf spot (Cercospora zeae-maydis)", "severity": "high",
        "symptoms": ["Long, narrow rectangular grey-brown lesions running between veins",
                     "Lesions join and blight the whole leaf at tasselling"],
        "organic": ["Bury or remove crop residue - the fungus survives on stubble",
                    "Foliar Trichoderma harzianum + neem oil 3 mL/L",
                    "Keep nitrogen balanced; deficiency worsens the disease"],
        "chemical": {"product": "Azoxystrobin 18.2 % + Difenoconazole 11.4 % SC",
                     "dose": "1 mL/L, one spray at VT and one at R1",
                     "note": "Do not spray within 30 days of harvest"},
        "prevention": ["Rotate with a non-graminaceous crop", "Choose tolerant hybrids"],
    },
    "corn_common_rust": {
        "crop": "corn", "condition": "Corn common rust (Puccinia sorghi)", "severity": "moderate",
        "symptoms": ["Cinnamon-brown powdery pustules on both leaf surfaces",
                     "Pustules darken to black at maturity"],
        "organic": ["Sulphur 80 % WP at 2 g/L has some suppressant effect",
                    "Early sowing escapes the cool-humid rust window"],
        "chemical": {"product": "Propiconazole 25 % EC",
                     "dose": "1 mL/L at first pustules, repeat after 15 days if needed",
                     "note": "Fungicide pays off only before 25 % leaf area is affected"},
        "prevention": ["Grow rust-resistant hybrids", "Avoid late planting"],
    },
    "corn_healthy": {
        "crop": "corn", "condition": "Healthy corn leaf", "severity": "low",
        "symptoms": ["Broad green leaf, no pustules or lesions"], "organic": [], "chemical": None,
        "prevention": ["Scout weekly from knee-high stage", "Keep the field free of volunteer maize"],
    },
    "grape_black_rot": {
        "crop": "grape", "condition": "Grape black rot (Guignardia bidwellii)", "severity": "high",
        "symptoms": ["Tan leaf spots with dark margins and black pycnidia dots",
                     "Berries shrivel into hard black mummies"],
        "organic": ["Remove mummies and infected canes during dormancy",
                    "Bordeaux mixture 1 % from bud break to pre-bloom",
                    "Canopy management: shoot thinning + leaf pulling for airflow"],
        "chemical": {"product": "Mancozeb 75 % WP or Myclobutanil 10 % WP",
                     "dose": "2 g/L, protectant schedule every 10-14 days pre-bloom",
                     "note": "Never exceed label doses; watch the pre-harvest interval"},
        "prevention": ["Keep the trellis open to sun and wind", "Avoid overhead irrigation"],
    },
    "grape_healthy": {
        "crop": "grape", "condition": "Healthy grape leaf", "severity": "low",
        "symptoms": ["Flat green leaf, intact margins"], "organic": [], "chemical": None,
        "prevention": ["Maintain the protectant schedule in the rainy season"],
    },
    "potato_early_blight": {
        "crop": "potato", "condition": "Potato early blight (Alternaria solani)", "severity": "moderate",
        "symptoms": ["Dark brown spots with concentric rings (target board) on older leaves",
                     "Leaves yellow around lesions and drop"],
        "organic": ["Balanced nitrogen + potassium; stressed plants are hit hardest",
                    "Neem oil 5 mL/L or Trichoderma soil application",
                    "Remove the lowest infected leaves to slow the upward spread"],
        "chemical": {"product": "Chlorothalonil 75 % WP or Mancozeb 75 % WP",
                     "dose": "2 g/L, 10-day interval; alternate with Azoxystrobin",
                     "note": "Early blight control is protective - spray before symptoms explode"},
        "prevention": ["3-year rotation away from solanaceous crops",
                       "Irrigate at the base; keep foliage dry"],
    },
    "potato_late_blight": {
        "crop": "potato", "condition": "Potato late blight (Phytophthora infestans)", "severity": "critical",
        "symptoms": ["Water-soaked grey-green patches that turn brown-black in cool wet weather",
                     "White fungal growth on the leaf underside; whole field can collapse in days"],
        "organic": ["Uproot and destroy (burn) severely infected plants immediately",
                    "Copper hydroxide 0.3 % as a protectant in the early stage",
                    "Improve drainage; never irrigate overhead"],
        "chemical": {"product": "Cymoxanil 8 % + Mancozeb 64 % WP or Metalaxyl 8 % + Mancozeb 64 % WP",
                     "dose": "2.5 g/L, spray immediately on the first lesion, repeat 7-10 days",
                     "note": "Late blight is an emergency - act the same day and report to the "
                             "local agriculture office"},
        "prevention": ["Plant certified seed tubers", "Destroy cull piles and volunteer plants",
                       "Stack fungicide protection when the forecast is cool and wet"],
    },
    "potato_healthy": {
        "crop": "potato", "condition": "Healthy potato leaf", "severity": "low",
        "symptoms": ["Even green leaf, no lesions"], "organic": [], "chemical": None,
        "prevention": ["Earth-up ridges to protect tubers", "Watch the forecast for cool-wet spells"],
    },
    "tomato_bacterial_spot": {
        "crop": "tomato", "condition": "Tomato bacterial spot (Xanthomonas spp.)", "severity": "high",
        "symptoms": ["Small greasy water-soaked spots that turn brown with yellow halos",
                     "Fruit shows raised scabby spots"],
        "organic": ["Prune and destroy infected foliage (disinfect tools each plant)",
                    "Copper hydroxide 0.2 % + Bacillus subtilis every 7-10 days",
                    "Never handle plants when leaves are wet"],
        "chemical": {"product": "Copper oxychloride 50 % WP + Streptocycline 100 ppm",
                     "dose": "3 g/L + 0.1 g/L, 7-10 day interval, max 4 sprays",
                     "note": "Copper-resistant strains exist - tank-mix with mancozeb if labelled"},
        "prevention": ["Hot-water-treat seed (52 C, 20 min)", "Drip irrigation + mulch",
                       "2-year rotation away from tomato/pepper"],
    },
    "tomato_early_blight": {
        "crop": "tomato", "condition": "Tomato early blight (Alternaria solani)", "severity": "moderate",
        "symptoms": ["Target-ring brown spots starting on the oldest leaves",
                     "Stem collar rot in seedlings; fruit shoulder lesions"],
        "organic": ["Mulch to block soil splash", "Remove lower leaves up to 30 cm",
                    "Neem oil 5 mL/L + copper on a 10-day cycle"],
        "chemical": {"product": "Mancozeb 75 % WP then Azoxystrobin 23 % SC",
                     "dose": "2 g/L then 1 mL/L, alternating 10-day intervals",
                     "note": "Alternate modes of action to avoid resistance"},
        "prevention": ["Stake and prune for airflow", "Rotate for 2-3 years", "Avoid overhead watering"],
    },
    "tomato_late_blight": {
        "crop": "tomato", "condition": "Tomato late blight (Phytophthora infestans)", "severity": "critical",
        "symptoms": ["Large greasy grey-brown blotches on leaves and stems",
                     "Firm dark greasy patches on green fruit; white mould underneath in the morning"],
        "organic": ["Remove and burn affected plants the same day",
                    "Copper hydroxide 0.3 % protectant on the remaining plants",
                    "Stop overhead irrigation completely"],
        "chemical": {"product": "Metalaxyl 8 % + Mancozeb 64 % WP or Cymoxanil + Mancozeb",
                     "dose": "2.5 g/L immediately, repeat every 7 days in wet weather",
                     "note": "Emergency disease - treat at once and inform nearby growers"},
        "prevention": ["Grow resistant hybrids where available", "Avoid dense planting",
                       "Spray protectively before a cool-wet forecast"],
    },
    "tomato_leaf_mold": {
        "crop": "tomato", "condition": "Tomato leaf mold (Passalora fulva)", "severity": "moderate",
        "symptoms": ["Pale yellow patches on the upper surface",
                     "Olive-green velvety mould on the corresponding lower surface"],
        "organic": ["Cut humidity: ventilate the polyhouse, water in the morning",
                    "Remove infected leaves and burn them",
                    "Potassium bicarbonate 5 g/L weekly"],
        "chemical": {"product": "Difenoconazole 25 % EC or Chlorothalonil 75 % WP",
                     "dose": "1 mL/L (or 2 g/L), 10-14 day interval",
                     "note": "Greenhouse humidity, not the fungicide, decides the outcome"},
        "prevention": ["Keep RH below 85 % and leaves dry overnight", "Space plants generously"],
    },
    "tomato_healthy": {
        "crop": "tomato", "condition": "Healthy tomato leaf", "severity": "low",
        "symptoms": ["Deep green leaf, no spotting or mould"], "organic": [], "chemical": None,
        "prevention": ["Weekly scouting, especially the lower canopy",
                       "Keep the leaf surface dry overnight"],
    },
    # ----------------------------------------------------------------------- #
    # Classes 19-38: the full PlantVillage 38-class set (the model's coverage)  #
    # ----------------------------------------------------------------------- #
    "apple_cedar_apple_rust": {
        "crop": "apple", "condition": "Apple cedar apple rust (Gymnosporangium juniperi-virginianae)",
        "severity": "moderate",
        "symptoms": ["Bright orange-yellow spots on the upper leaf surface",
                     "Small black dots inside the spots; later, tube-like spore horns underneath"],
        "organic": ["Remove galls from nearby juniper/cedar hosts before spring rains",
                    "Sulphur 80 % WP as a protectant during bloom",
                    "Collect and destroy fallen leaves in autumn"],
        "chemical": {"product": "Myclobutanil 10 % WP or Difenoconazole 25 % EC",
                     "dose": "0.4 mL/L Myclobutanil, 3 sprays at 10-day intervals from pink bud",
                     "note": "The fungus needs both hosts: breaking the juniper link is half the cure"},
        "prevention": ["Plant resistant apple varieties where rust is endemic",
                       "Keep apples away from ornamental junipers"],
    },
    "blueberry_healthy": {
        "crop": "blueberry", "condition": "Healthy blueberry leaf", "severity": "low",
        "symptoms": ["Glossy green oval leaf, red-tinged only in autumn as normal"],
        "organic": [], "chemical": None,
        "prevention": ["Keep soil pH 4.5-5.5 - the single biggest blueberry health factor",
                       "Mulch with pine bark and never let the root zone dry out"],
    },
    "cherry_healthy": {
        "crop": "cherry", "condition": "Healthy cherry leaf", "severity": "low",
        "symptoms": ["Deep green serrated leaf, no shot-holes or powder"],
        "organic": [], "chemical": None,
        "prevention": ["Prune for an open centre so leaves dry quickly",
                       "Scout after each rain for shot-hole and mildew"],
    },
    "cherry_powdery_mildew": {
        "crop": "cherry", "condition": "Cherry powdery mildew (Podosphaera clandestina)",
        "severity": "moderate",
        "symptoms": ["White powdery patches on young leaves and shoot tips",
                     "Leaves curl, look silvery, and stunted shoots stay small"],
        "organic": ["Prune out crowded growth to open the canopy",
                    "Potassium bicarbonate 5 g/L every 7 days",
                    "Wettable sulphur 2 g/L - never above 30 °C"],
        "chemical": {"product": "Myclobutanil 10 % WP or Hexaconazole 5 % EC",
                     "dose": "0.4 mL/L Myclobutanil, cover new growth until it hardens",
                     "note": "Powdery mildews thrive in dry heat, not in rain - do not spray in the sun's peak"},
        "prevention": ["Avoid excess nitrogen - soft growth invites mildew",
                       "Remove and burn infected shoot tips during pruning"],
    },
    "corn_northern_leaf_blight": {
        "crop": "corn", "condition": "Corn northern leaf blight (Exserohilum turcicum)",
        "severity": "high",
        "symptoms": ["Long cigar-shaped grey-green lesions 3-15 cm on lower leaves first",
                     "Lesions turn tan with dark borders and can blight whole leaves"],
        "organic": ["Deep-plough crop residue after harvest",
                    "Spray Bacillus subtilis + neem oil 3 mL/L at first symptom",
                    "Keep potash adequate; deficiency worsens the blight"],
        "chemical": {"product": "Propiconazole 25 % EC or Azoxystrobin 23 % SC",
                     "dose": "1 mL/L, spray at first lesions and again at tasselling if it spreads",
                     "note": "Stop spraying 30 days before harvest or silage cutting"},
        "prevention": ["Rotate to a non-cereal for one season",
                       "Sow blight-tolerant hybrids; avoid overhead irrigation late in the day"],
    },
    "grape_esca": {
        "crop": "grape", "condition": "Grape esca / black measles (Phaeomoniella, Phaeoacremonium spp.)",
        "severity": "high",
        "symptoms": ["Interveinal yellow-to-red streaks that leave green bands along the veins",
                     "Sudden leaf drop or whole-vine collapse in hot weather"],
        "organic": ["Mark and prune the affected vine last, cleaning tools between vines",
                    "Apply Trichoderma to pruning wounds",
                    "Remove dead wood right down to healthy tissue"],
        "chemical": {"product": "No effective cure once inside the wood - protect cuts instead",
                     "dose": "Painting pruning wounds with a wound sealant or Bordeaux paste",
                     "note": "Esca lives in the trunk; treatment is surgery and prevention, not spraying"},
        "prevention": ["Prune late, in dry weather, and never in the rain",
                       "Replant with clean nursery material and renew the trunk when symptoms return"],
    },
    "grape_leaf_blight": {
        "crop": "grape", "condition": "Grape leaf blight (Pseudocercospora vitis)",
        "severity": "moderate",
        "symptoms": ["Brown angular patches between the veins, with a yellow halo",
                     "Fruit may shrivel and grapes fail to colour"],
        "organic": ["Collect and burn fallen leaves - the fungus overwinters there",
                    "Copper oxychloride 3 g/L as a protective spray",
                    "Open the canopy with leaf removal around the bunch zone"],
        "chemical": {"product": "Mancozeb 75 % WP or Difenoconazole 25 % EC",
                     "dose": "2 g/L Mancozeb at 12-15 day intervals after fruit set",
                     "note": "Alternate actives so the fungus does not build resistance"},
        "prevention": ["Keep the canopy ventilated", "Avoid overhead irrigation"],
    },
    "orange_haunglongbing": {
        "crop": "orange", "condition": "Citrus greening / HLB (Candidatus Liberibacter asiaticus)",
        "severity": "critical",
        "symptoms": ["Blotchy mottling with the leaf vein staying green - the classic asymmetric pattern",
                     "Small lopsided fruit that stays green at the bottom and drops"],
        "organic": ["Pull and destroy the tree - this disease has no cure once infected",
                    "Keep the psyllid vector down with yellow sticky traps",
                    "Do not take budwood from a symptomatic tree"],
        "chemical": {"product": "No cure - manage the vector with Imidacloprid 17.8 % SL",
                     "dose": "0.3 mL/L as soil drench, or 0.5 mL/L foliar, 3-week intervals",
                     "note": "Report to the local horticulture officer: HLB is a notifiable disease"},
        "prevention": ["Use certified disease-free nursery plants only",
                       "Control the Asian citrus psyllid year-round, especially new flush"],
    },
    "peach_bacterial_spot": {
        "crop": "peach", "condition": "Peach bacterial spot (Xanthomonas arboricola pv. pruni)",
        "severity": "high",
        "symptoms": ["Small water-soaked spots that turn purple-brown and fall out, leaving shot-holes",
                     "Fruit develops dark sunken cracked spots"],
        "organic": ["Copper oxychloride 3 g/L at leaf fall and again before bud break",
                    "Remove and burn heavily infected shoots in winter",
                    "Keep the tree vigorous - wind damage opens the door"],
        "chemical": {"product": "Oxytetracycline or Copper hydroxide + Mancozeb",
                     "dose": "2.5 g/L copper at 10-14 day intervals until harvest",
                     "note": "Do not spray copper in hot sun - it burns peach leaves"},
        "prevention": ["Plant resistant varieties", "Shelter the block from drying winds"],
    },
    "peach_healthy": {
        "crop": "peach", "condition": "Healthy peach leaf", "severity": "low",
        "symptoms": ["Long narrow bright green leaf, no shot-holes or spots"],
        "organic": [], "chemical": None,
        "prevention": ["Dormant copper spray once a year for leaf curl",
                       "Winter pruning to keep the centre open"],
    },
    "raspberry_healthy": {
        "crop": "raspberry", "condition": "Healthy raspberry leaf", "severity": "low",
        "symptoms": ["Deep green serrated leaf, pale underside, no spots"],
        "organic": [], "chemical": None,
        "prevention": ["Thin canes so air moves through the row",
                       "Cut out and burn old fruiting canes after harvest"],
    },
    "soybean_healthy": {
        "crop": "soybean", "condition": "Healthy soybean leaf", "severity": "low",
        "symptoms": ["Fresh green trifoliate leaf, no lesions or mosaic"],
        "organic": [], "chemical": None,
        "prevention": ["Rotate with a cereal every second year",
                       "Keep the field free of volunteer soybean and weeds"],
    },
    "squash_powdery_mildew": {
        "crop": "squash", "condition": "Squash powdery mildew (Podosphaera xanthii)",
        "severity": "moderate",
        "symptoms": ["White floury patches on the upper leaf surface and stems",
                     "Leaves yellow, dry out and the fruit is sunburnt and small"],
        "organic": ["Milk spray 1:9 with water, weekly, in the morning",
                    "Potassium bicarbonate 5 g/L on a 7-day rotation",
                    "Remove the oldest infected leaves to slow the spread"],
        "chemical": {"product": "Hexaconazole 5 % EC or Wettable sulphur 80 % WP",
                     "dose": "1 mL/L hexaconazole, or 2 g/L sulphur, 10-day intervals",
                     "note": "Alternate actives; powdery mildew develops resistance quickly"},
        "prevention": ["Water at the roots, keep the foliage dry",
                       "Grow tolerant varieties and give the vines room"],
    },
    "strawberry_healthy": {
        "crop": "strawberry", "condition": "Healthy strawberry leaf", "severity": "low",
        "symptoms": ["Tri-lobed green leaf with a clean edge, no purple blotches"],
        "organic": [], "chemical": None,
        "prevention": ["Renew the bed every 2-3 years with clean runners",
                       "Straw mulch under the fruit to stop soil splash"],
    },
    "strawberry_leaf_scorch": {
        "crop": "strawberry", "condition": "Strawberry leaf scorch (Diplocarpon earlianum)",
        "severity": "moderate",
        "symptoms": ["Many small dark purple spots that join up, so the leaf looks scorched",
                     "Leaf edges dry and curl upward in severe attacks"],
        "organic": ["Remove old infected leaves after harvest and burn them",
                    "Copper oxychloride 3 g/L after renovation",
                    "Keep the bed weed-free so air moves through"],
        "chemical": {"product": "Captan 50 % WP or Difenoconazole 25 % EC",
                     "dose": "2 g/L Captan at 10-14 day intervals from early bloom",
                     "note": "Stop 7 days before picking - fruit is eaten fresh"},
        "prevention": ["Plant certified runners", "Avoid overhead irrigation in the evening"],
    },
    "tomato_septoria": {
        "crop": "tomato", "condition": "Tomato septoria leaf spot (Septoria lycopersici)",
        "severity": "high",
        "symptoms": ["Many small round spots with grey centres and dark rims, starting low on the plant",
                     "Spots carry tiny black dots and leaves die from the bottom up"],
        "organic": ["Pull off the lowest infected leaves and burn them",
                    "Stake and mulch so soil cannot splash onto the leaves",
                    "Copper oxychloride 3 g/L every 10 days"],
        "chemical": {"product": "Chlorothalonil 75 % WP or Mancozeb 75 % WP",
                     "dose": "2 g/L at 7-10 day intervals while it is humid",
                     "note": "Alternate with a systemic (difenoconazole) to slow resistance"},
        "prevention": ["Rotate away from tomato and potato for 2 years",
                       "Water at the base, early in the day"],
    },
    "tomato_spider_mites": {
        "crop": "tomato", "condition": "Tomato two-spotted spider mite (Tetranychus urticae)",
        "severity": "high",
        "symptoms": ["Fine pale stippling over the leaf, then a bronzed dusty look",
                     "Fine webbing on the underside and along the stem"],
        "organic": ["Jet of water under the leaves, twice a week - mites hate wet",
                    "Neem oil 5 mL/L or soap solution, sprayed underneath the leaf",
                    "Release predatory mites (Phytoseiulus persimilis) if available"],
        "chemical": {"product": "Spiromesifen 22.9 % SC or Abamectin 1.9 % EC",
                     "dose": "0.8 mL/L spiromesifen, spray the leaf undersides",
                     "note": "Mites resist fast: rotate actives, never spray the same one twice in a row"},
        "prevention": ["Avoid dusty dry borders - keep them watered",
                       "Do not over-use broad-spectrum insecticides; they kill the predators too"],
    },
    "tomato_target_spot": {
        "crop": "tomato", "condition": "Tomato target spot (Corynespora cassiicola)",
        "severity": "moderate",
        "symptoms": ["Brown spots with clear concentric rings, like a target board",
                     "Fruit gets dark pitted spots that never colour properly"],
        "organic": ["Remove and burn affected leaves; do not compost them",
                    "Copper oxychloride 3 g/L plus a sticker every 10 days",
                    "Open the canopy: this fungus loves a humid, crowded crop"],
        "chemical": {"product": "Difenoconazole 25 % EC or Azoxystrobin 23 % SC",
                     "dose": "1 mL/L, alternate the two, 10-14 day interval",
                     "note": "Spray in the morning so the canopy dries before night"},
        "prevention": ["Rotate with maize or a cereal", "Mulch to stop soil splash"],
    },
    "tomato_mosaic_virus": {
        "crop": "tomato", "condition": "Tomato mosaic virus (ToMV)",
        "severity": "high",
        "symptoms": ["Light and dark green mosaic mottling, often puckered or fern-like leaves",
                     "Plants are stunted and fruit can show internal browning"],
        "organic": ["Pull out and destroy infected plants - there is no cure for a virus",
                    "Dip hands and tools in milk or a soap solution between plants",
                    "Control aphids and thrips which carry the virus"],
        "chemical": {"product": "No direct cure - manage the vectors",
                     "dose": "Imidacloprid 17.8 % SL 0.3 mL/L only if aphids/thrips are building up",
                     "note": "Never save seed from an infected crop; the virus passes through it"},
        "prevention": ["Use ToMV-resistant varieties and certified seed",
                       "Wash hands before handling plants, especially after smoking/tobacco"],
    },
    "tomato_yellow_leaf_curl_virus": {
        "crop": "tomato", "condition": "Tomato yellow leaf curl virus (TYLCV)",
        "severity": "critical",
        "symptoms": ["New leaves curl upward and are much smaller, with yellow edges",
                     "The plant stays bushy and stunted and sets almost no fruit"],
        "organic": ["Uproot and destroy infected plants immediately - no cure exists",
                    "Use yellow sticky traps and a fine net nursery",
                    "Spray neem oil 5 mL/L to suppress the whitefly that spreads it"],
        "chemical": {"product": "Vector control: Imidacloprid 17.8 % SL or Diafenthiuron 50 % WP",
                     "dose": "0.3 mL/L imidacloprid as a soil drench at transplanting",
                     "note": "Prevention at the seedling stage decides the whole season"},
        "prevention": ["Grow TYLCV-resistant hybrids",
                       "Keep the field whitefly-free for the first 6 weeks after transplanting"],
    },
}


# --------------------------------------------------------------------------- #

# The 38-class PlantVillage vocabulary spells the pepper classes `pepper_*`; the
# 18-class generation called them `bell_pepper_*`. Both spellings must reach the same
# advice, so the old keys are aliased onto the new entries instead of duplicated.
ALIASES = {"bell_pepper_bacterial_spot": "pepper_bacterial_spot",
           "bell_pepper_healthy": "pepper_healthy"}
for _old, _new in ALIASES.items():
    if _new in KB and _old not in KB:
        KB[_old] = KB[_new]

  
def crop_label(slug: str | None, lang: str | None = None) -> str:
    entry = KB.get(slug or "", {})
    crop = entry.get("crop")
    if not crop:
        return "Unknown crop"
    return CROPS.get(crop, {}).get(lang or "en") or CROPS.get(crop, {}).get("en", crop)


def condition_name(slug: str | None, lang: str | None = None) -> str | None:
    """Localized display name for a class slug ('tomato_late_blight' -> 'ટામેટું મોડો સુકારો …').

    Used by the sample picker and the results header so the UI never shows a raw
    slug next to translated text. Scientific names stay in Latin script.
    """
    if not slug:
        return None
    entry = KB.get(slug)
    text = (entry or {}).get("condition") or str(slug).replace("_", " ")
    return localize_condition(text, lang)


def is_healthy(slug: str) -> bool:
    return slug.endswith("_healthy")


def upgrade(risk: str, steps: int = 1) -> str:
    i = RISK_ORDER.index(risk) if risk in RISK_ORDER else 0
    return RISK_ORDER[min(len(RISK_ORDER) - 1, i + steps)]


def risk_label(risk: str, lang: str | None = None) -> str:
    return t(f"risk_{risk}" if risk in RISK_ORDER else "risk_moderate", lang)


def assess_risk(
    slug: str,
    confidence: float,
    weather: dict[str, Any] | None = None,
    lang: str | None = None,
) -> dict[str, Any]:
    """Combine KB severity, model confidence and weather context into a risk card."""
    lang = normalise(lang)
    kb = KB.get(slug, {})
    confidence = float(confidence or 0.0)
    notes: list[str] = []

    if is_healthy(slug):
        risk = "low"
        notes.append(say("r_healthy", lang))
    elif confidence >= KB_SEVERITY_CONF:
        risk = kb.get("severity", "moderate")
        notes.append(say("r_conf_high", lang, conf=f"{confidence:.0%}",
                         thr=f"{KB_SEVERITY_CONF:.0%}"))
    elif confidence >= LOW_CONF:
        risk = "moderate"
        notes.append(say("r_conf_mid", lang, conf=f"{confidence:.0%}",
                         lo=f"{LOW_CONF:.0%}", hi=f"{KB_SEVERITY_CONF:.0%}"))
    else:
        risk = "moderate"
        notes.append(t("confidence_low", lang))

    weather = weather or {}
    rain_p = weather.get("rain_probability_pct")
    rh = weather.get("humidity_pct")
    humid = (isinstance(rh, (int, float)) and rh >= 80) or \
            (isinstance(rain_p, (int, float)) and rain_p >= 60) or \
            bool(weather.get("is_rainy_now"))
    if humid and not is_healthy(slug):
        new_risk = upgrade(risk)
        if new_risk != risk:
            notes.append(say("r_humid", lang))
        risk = new_risk

    # KB prose comes from the overlay, so symptoms/actions/prevention are localized
    # while product names and doses stay exactly as the label prints them.
    kb_display = kb_i18n.localize_kb({slug: kb}, lang).get(slug, kb)
    return {
        "slug": slug,
        "crop": crop_label(slug, lang),
        "condition": kb.get("condition", slug),
        "condition_localized": localize_condition(kb.get("condition", slug), lang),
        "severity_kb": kb.get("severity", "moderate"),
        "risk": risk,
        "risk_label": risk_label(risk, lang),
        "is_healthy": is_healthy(slug),
        "confidence": round(confidence, 4),
        "confidence_band": ("high" if confidence >= KB_SEVERITY_CONF
                            else "medium" if confidence >= LOW_CONF else "low"),
        # the UI shows the *_label fields; the raw slugs stay for tests and the assistant
        "confidence_band_label": say("band_" + ("high" if confidence >= KB_SEVERITY_CONF
                                                else "medium" if confidence >= LOW_CONF else "low"), lang),
        "severity_label": say("sev_" + str(kb.get("severity", "moderate")), lang),
        "advisory_level_label": say({"none": "adv_none", "observe": "adv_observe",
                                     "act-soon": "adv_soon", "act-now": "adv_now",
                                     "emergency": "adv_emergency"}[
            ("none" if (is_healthy(slug) and risk == "low")
             else "observe" if risk == "low"
             else "act-soon" if risk == "moderate"
             else "act-now" if risk == "high" else "emergency")], lang),
        "notes": notes,
        "symptoms": kb_display.get("symptoms", []),
        "organic_actions": kb_display.get("organic", []),
        "chemical_option": kb_display.get("chemical"),
        "prevention": kb_display.get("prevention", []),
        "advisory_level": ("none" if (is_healthy(slug) and risk == "low")
                           else "observe" if risk == "low"
                           else "act-soon" if risk == "moderate"
                           else "act-now" if risk == "high" else "emergency"),
        "source": say("r_source", lang),
    }


def _tagged(items: list[dict[str, str]], lang: str) -> list[dict[str, str]]:
    """Attach the display tags. Both exits from `actions_for` go through here - the
    healthy path returns early, and forgetting it is exactly how a tag goes missing."""
    for a in items:
        a["priority_label"] = say("p_" + a["priority"], lang)
        a["kind_label"] = say("k_" + a["kind"], lang)
    return items


def actions_for(slug: str, risk: str, lang: str | None = None) -> list[dict[str, str]]:
    """Flatten the KB into a prioritised, check-off-able action list.

    Content comes from the KB through kb_i18n, so the list is in the requested
    language; product names and doses stay verbatim in every language.
    """
    lang = normalise(lang)
    kb = kb_i18n.localize_kb({slug: KB.get(slug, {})}, lang).get(slug, KB.get(slug, {}))
    out: list[dict[str, str]] = []
    if is_healthy(slug):
        out.append({"priority": "routine", "kind": "scout", "text": say("a_scout_only", lang)})
        for p in kb.get("prevention", []):
            out.append({"priority": "routine", "kind": "prevention", "text": p})
        return _tagged(out, lang)
    for i, item in enumerate(kb.get("organic", [])):
        out.append({"priority": "immediate" if i == 0 else "today", "kind": "organic", "text": item})
    chem = kb.get("chemical")
    if chem and risk in ("high", "critical"):
        out.append({"priority": "today", "kind": "chemical",
                    "text": say("a_chem_strong", lang, product=chem["product"], dose=chem["dose"],
                                note=chem.get("note", ""))})
    elif chem:
        out.append({"priority": "later", "kind": "chemical",
                    "text": say("a_chem_mild", lang, product=chem["product"], dose=chem["dose"])})
    for p in kb.get("prevention", []):
        out.append({"priority": "routine", "kind": "prevention", "text": p})
    return _tagged(out, lang)


def kb_coverage() -> dict[str, int]:
    """Small self-check used by the tests: KB completeness for every class."""
    problems = 0
    for slug, e in KB.items():
        for field in ("crop", "condition", "severity", "symptoms", "prevention"):
            if not e.get(field):
                problems += 1
        if not is_healthy(slug) and not e.get("organic"):
            problems += 1
    return {"classes": len(KB), "problems": problems}
