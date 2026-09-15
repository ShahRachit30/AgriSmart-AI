#!/usr/bin/env python3
"""Re-apply the farmer pass parts that live in i18n.js, styles.css and Results.

`scripts/apply_farmer_pass.py` covers the dashboard/upload/camera side; this covers
the remaining three files. Both are idempotent-guarded by exact anchors, and this
script is kept in the repo so a reverted workspace can be rebuilt in one command:

    python scripts/apply_farmer_pass.py && python scripts/apply_farmer_results_i18n_css.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
done = []


def edit(path: Path, pairs: list[tuple[str, str, str]]) -> None:
    s = path.read_text()
    for old, new, label in pairs:
        assert s.count(old) == 1, f"{path.name}/{label}: {s.count(old)} matches"
        s = s.replace(old, new)
        done.append(f"{path.name}: {label}")
    path.write_text(s)


# ------------------------------------------------------------------ i18n.js
edit(ROOT / "app" / "frontend" / "src" / "i18n.js", [
    ("  dashboard: { en: 'Dashboard', hi: 'डैशबोर्ड', gu: 'ડેશબોર્ડ' },\n"
     "  results: { en: 'Results', hi: 'परिणाम', gu: 'પરિણામ' },",
     """  // plain language on purpose: "Dashboard" means nothing to a farmer
  dashboard: { en: 'Check a leaf', hi: 'पत्ती जाँचें', gu: 'પાન તપાસો' },
  results: { en: 'Result & advice', hi: 'परिणाम व सलाह', gu: 'પરિણામ અને સલાહ' },
  results_title: { en: 'Your result', hi: 'आपका परिणाम', gu: 'તમારું પરિણામ' },
  language: { en: 'Language', hi: 'भाषा', gu: 'ભાષા' },
  choose_language: { en: 'Choose your language', hi: 'अपनी भाषा चुनें', gu: 'તમારી ભાષા પસંદ કરો' },
  coverage: {
    en: '{d} diseases · {c} crops',
    hi: '{d} रोग · {c} फसलें',
    gu: '{d} રોગ · {c} પાક',
  },""", "tab labels + coverage"),

    ("  choose_photo: { en: 'Choose photo', hi: 'फोटो चुनें', gu: 'ફોટો પસંદ કરો' },",
     """  choose_photo: { en: 'Choose photo', hi: 'फोटो चुनें', gu: 'ફોટો પસંદ કરો' },
  which_photo: {
    en: 'Photograph one leaf - or pick one you already took.',
    hi: 'एक पत्ती की फोटो लें - या पहले ली हुई फोटो चुनें।',
    gu: 'એક પાનનો ફોટો લો - અથવા પહેલાં લીધેલો ફોટો પસંદ કરો.',
  },
  capture_take: { en: 'Take photo', hi: 'फोटो लें', gu: 'ફોટો લો' },
  capture_close: { en: 'Close camera', hi: 'कैमरा बंद करें', gu: 'કૅમેરો બંધ કરો' },
  capture_shoot: { en: 'Capture leaf photo', hi: 'पत्ती की फोटो लें', gu: 'પાનનો ફોટો લો' },
  capture_switch: { en: 'Switch camera', hi: 'कैमरा बदलें', gu: 'કૅમેરો બદલો' },
  capture_starting: { en: 'Starting the camera…', hi: 'कैमरा शुरू हो रहा है…', gu: 'કૅમેરો શરૂ થાય છે…' },
  capture_tip: {
    en: 'Fill the frame with one leaf and hold steady.',
    hi: 'एक ही पत्ती फ्रेम में रखें और स्थिर रहें।',
    gu: 'એક જ પાન ફ્રેમમાં રાખો અને સ્થિર રહો.',
  },
  capture_denied: {
    en: 'Camera access is blocked.',
    hi: 'कैमरे की अनुमति बंद है।',
    gu: 'કૅમેરાની પરવાનગી બંધ છે.',
  },
  capture_unavailable: {
    en: 'No camera found on this device.',
    hi: 'इस डिवाइस में कैमरा नहीं मिला।',
    gu: 'આ ઉપકરણમાં કૅમેરો મળ્યો નથી.',
  },
  capture_failed: {
    en: 'The camera could not be started.',
    hi: 'कैमरा शुरू नहीं हो सका।',
    gu: 'કૅમેરો શરૂ થઈ શક્યો નથી.',
  },
  capture_escape_hint: {
    en: 'You can still use your phone camera app or choose a photo - either works.',
    hi: 'आप फ़ोन का कैमरा ऐप इस्तेमाल कर सकते हैं या फोटो चुन सकते हैं - दोनों काम करते हैं।',
    gu: 'તમે ફોનની કૅમેરા ઍપ વાપરી શકો છો કે ફોટો પસંદ કરી શકો છો - બંને ચાલે છે.',
  },
  capture_use_phone: { en: 'Use phone camera', hi: 'फ़ोन का कैमरा', gu: 'ફોનનો કૅમેરો' },
  capture_choose_instead: { en: 'Choose a photo instead', hi: 'फोटो चुनें', gu: 'ફોટો પસંદ કરો' },
  pick_another: { en: 'Choose a different photo', hi: 'दूसरी फोटो चुनें', gu: 'બીજો ફોટો પસંદ કરો' },
  retake: { en: 'Take another photo', hi: 'दूसरी फोटो लें', gu: 'બીજો ફોટો લો' },
  listen: { en: 'Listen', hi: 'सुनें', gu: 'સાંભળો' },
  listen_stop: { en: 'Reading…', hi: 'सुनाया जा रहा है…', gu: 'સંભળાવાય છે…' },
  listen_unsupported: {
    en: 'This browser cannot read the result aloud.',
    hi: 'यह ब्राउज़र नतीजा बोलकर नहीं सुना सकता।',
    gu: 'આ બ્રાઉઝર પરિણામ બોલીને સંભળાવી શકતું નથી.',
  },
  leaf_checked: { en: 'leaf photo checked', hi: 'पत्ती की फोटो जाँची गई', gu: 'પાનનો ફોટો તપાસ્યો' },
  leaf_checked_hint: {
    en: 'Confidence that the photo really is a leaf, not an object.',
    hi: 'यह भरोसा कि फोटो में वाकई पत्ती है, कोई वस्तु नहीं।',
    gu: 'વિશ્વાસ કે ફોટોમાં ખરેખર પાન છે, કોઈ વસ્તુ નહીં.',
  },
  plain_healthy: { en: 'Your leaf looks healthy', hi: 'आपकी पत्ती स्वस्थ लग रही है', gu: 'તમારું પાન તંદુરસ્ત લાગે છે' },
  plain_disease: { en: 'We found a disease on this leaf', hi: 'इस पत्ती में रोग मिला है', gu: 'આ પાનમાં રોગ મળ્યો છે' },
  plain_confident: {
    en: 'We are {c} sure of this.',
    hi: 'हमें इसका {c} भरोसा है।',
    gu: 'અમને આનો {c} વિશ્વાસ છે.',
  },
  plain_unsure: {
    en: 'We are only {c} sure - please check the leaf again or ask your local officer.',
    hi: 'हमें सिर्फ़ {c} भरोसा है - पत्ती फिर देखें या स्थानीय कृषि अधिकारी से पूछें।',
    gu: 'અમને ફક્ત {c} વિશ્વાસ છે - પાન ફરી તપાસો કે સ્થાનિક અધિકારીને પૂછો.',
  },
  todo_title: { en: 'What to do today', hi: 'आज क्या करें', gu: 'આજે શું કરવું' },""",
     "capture + verdict keys"),

    ("  crop_bell_pepper: { en: 'bell pepper', hi: 'शिमला मिर्च', gu: 'શિમલા મરચું' },",
     """  crop_bell_pepper: { en: 'bell pepper', hi: 'शिमला मिर्च', gu: 'શિમલા મરચું' },
  crop_orange: { en: 'orange', hi: 'संतरा', gu: 'સંતરું' },
  crop_peach: { en: 'peach', hi: 'आड़ू', gu: 'આડૂ' },
  crop_cherry: { en: 'cherry', hi: 'चेरी', gu: 'ચેરી' },
  crop_strawberry: { en: 'strawberry', hi: 'स्ट्रॉबेरी', gu: 'સ્ટ્રોબેરી' },
  crop_blueberry: { en: 'blueberry', hi: 'ब्लूबेरी', gu: 'બ્લૂબેરી' },
  crop_raspberry: { en: 'raspberry', hi: 'रास्पबेरी', gu: 'રાસ્પબેરી' },
  crop_squash: { en: 'squash', hi: 'कद्दू वर्ग', gu: 'કોળું વર્ગ' },
  crop_soybean: { en: 'soybean', hi: 'सोयाबीन', gu: 'સોયાબીન' },""",
     "crop names"),

    ("export const LANG_LABEL = { en: 'EN', hi: 'हि', gu: 'ગુ' }",
     "export const LANG_LABEL = { en: 'EN', hi: 'हिंदी', gu: 'ગુજરાતી' }",
     "language button labels"),
])

# ------------------------------------------------------------------- App.jsx
edit(ROOT / "app" / "frontend" / "src" / "App.jsx", [
    ("""function Results({ t, analysis, chat, question, setQuestion, ask, previewUrl,
  relocalizing, assistantEngine, onStartNew }) {""",
     """function Results({ t, lang, analysis, chat, question, setQuestion, ask, previewUrl,
  relocalizing, assistantEngine, onStartNew, openCamera }) {""", "results signature"),

    ("""        <h2>{t('results')}</h2>
        <p className="muted">{t('no_analysis')}</p>""",
     """        <h2>{t('results_title')}</h2>
        <p className="muted">{t('no_analysis')}</p>""", "empty heading"),

    ("""          <div className="eyebrow">{t('at_a_glance')}</div>
          <h2 className="headline">{p ? (p.condition_localized || p.condition) : t('no_photo_note')}</h2>
          {p && (
            <p className="muted small tight">
              {p.crop_localized || p.crop} · {t('confidence')} {pct(p.confidence)}
            </p>
          )}
          {narrative && <p className="verdict-text">{narrative}</p>}""",
     """          <div className="eyebrow">{t('at_a_glance')}</div>
          {p && (
            <p className={`plain-kicker ${p.healthy ? 'ok' : 'bad'}`}>
              {p.healthy ? t('plain_healthy') : t('plain_disease')}
            </p>
          )}
          <h2 className="headline">{p ? (p.condition_localized || p.condition) : t('no_photo_note')}</h2>
          {p && (
            <>
              <p className="muted small tight">
                {p.crop_localized || p.crop} · {t('confidence')} {pct(p.confidence)}
              </p>
              <p className="plain-sentence">
                {p.confidence >= 0.75
                  ? t('plain_confident', { c: pct(p.confidence) })
                  : t('plain_unsure', { c: pct(p.confidence) })}
              </p>
            </>
          )}
          {p?.leaf_check?.p_leaf != null && (
            <span className="leaf-ok" title={t('leaf_checked_hint')}>
              ✓ {t('leaf_checked')} · {pct(p.leaf_check.p_leaf)}
            </span>
          )}
          {narrative && <p className="verdict-text">{narrative}</p>}
          {p && (
            <div className="actions-bar">
              <ListenButton t={t} lang={lang}
                text={[p.condition_localized || p.condition, p.crop_localized || p.crop,
                  t('confidence'), pct(p.confidence), narrative].filter(Boolean).join('. ')} />
              <button type="button" className="ghost" onClick={openCamera}>
                📸 {t('retake')}
              </button>
            </div>
          )}""", "plain verdict + listen + retake"),

    ("""      <div className="grid">
        <Card title={t('prediction')}""",
     """      {/* The one thing a farmer came for, in order, with the biggest type on the
          page. The detailed cards below are for whoever wants the full picture. */}
      {actions?.length > 0 && (
        <section className="card todo">
          <h3>✅ {t('todo_title')}</h3>
          <ol className="todo-list">
            {actions.map((a, i) => (
              <li key={i}>
                <span className="step-no" aria-hidden>{i + 1}</span>
                <span>
                  <b>{a.text}</b>
                  {a.kind_label && <span className="muted small"> · {a.kind_label}</span>}
                  {a.priority && (
                    <span className={`tag ${a.priority}`}>{a.priority_label || a.priority}</span>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <div className="grid">
        <Card title={t('prediction')}""", "todo card"),
])

# ---------------------------------------------------------------- styles.css
css = ROOT / "app" / "frontend" / "src" / "styles.css"
s = css.read_text()
for old, new in [("--green-500: #2e8b45;", "--green-500: #237036;"),
                 ("--red: #d64545;", "--red: #c22f2f;"),
                 ("--muted: #6b7f70;", "--muted: #57695b;")]:
    if old in s:
        s = s.replace(old, new)
        done.append(f"styles.css: palette {old.split(':')[0]}")
s = s.replace("#9a6b00", "#8a5f00").replace("#b35300", "#a34a00")

if "Farmer pass" not in s:
    s += """

/* ============================================================================
   Farmer pass - legibility first.
   The person using this holds a phone in daylight, often with reading glasses,
   and does not read English. So: bigger base type, thumb-sized targets, one
   obvious primary action per card, and plain words. Contrast values here are
   asserted in tests/test_ui_legibility.py.
   ========================================================================== */
body { font-size: 17px; }
.lead { font-size: 18px; font-weight: 600; margin: 6px 0 12px; }
.field-label { font-size: 16px; font-weight: 700; margin: 4px 0 8px; }

/* tap targets: nothing a farmer taps is smaller than a thumb */
button, .primary, .ghost, label.primary { min-height: 48px; }
.primary.big, .ghost.big, button.big { min-height: 56px; font-size: 17px; padding: 12px 18px; }
button + button, .primary + .ghost, .ghost + .primary { margin-left: 8px; }

header .coverage { font-size: 12.5px; opacity: .95; margin-top: 3px; font-weight: 600; }
.lang-btn { min-width: 84px; min-height: 46px; font-size: 15px; font-weight: 700; }
.lang-btn.active { outline: 3px solid var(--lime); outline-offset: 1px; }

/* crop picker: picture + word, big enough to hit with a thumb */
.chips.crops { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 14px; }
.chip.crop {
  min-height: 48px; padding: 8px 14px; border-radius: 999px; border: 2px solid var(--line);
  background: #fff; font-size: 15.5px; font-weight: 600; cursor: pointer; color: var(--ink);
}
.chip.crop.on { border-color: var(--green-500); background: #eafaee; box-shadow: var(--shadow-sm); }
.chip.crop:active { transform: scale(.98); }

/* the verdict, in words a farmer uses */
.plain-kicker { margin: 2px 0 0; font-size: 15px; font-weight: 800; letter-spacing: .02em; }
.plain-kicker.ok { color: #1e7a37; }
.plain-kicker.bad { color: #b02121; }
.plain-sentence { font-size: 17px; margin: 6px 0 2px; }
.leaf-ok {
  display: inline-block; margin-top: 8px; padding: 5px 10px; border-radius: 999px;
  background: #e5f6e8; color: #1e7a37; font-size: 13.5px; font-weight: 700;
}

/* "what to do today": the one card a farmer really reads */
.card.todo { border-left: 6px solid var(--green-500); background: #f7fdf8; }
.card.todo h3 { margin: 0 0 10px; font-size: 19px; }
.todo-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
.todo-list li { display: flex; gap: 12px; align-items: flex-start; font-size: 17px; line-height: 1.45; }
.step-no {
  flex: 0 0 34px; width: 34px; height: 34px; border-radius: 50%; background: var(--green-700);
  color: #fff; font-weight: 800; display: grid; place-items: center; font-size: 16px;
}
.todo-list .tag { margin-left: 8px; }

/* a refusal is advice, not an error */
.card.notice { border-left: 6px solid var(--amber); background: #fffdf3; }
.notice-head { display: flex; gap: 12px; align-items: flex-start; font-size: 17px; }

/* live capture */
.capture { margin: 10px 0; display: grid; gap: 8px; }
.capture-video {
  width: 100%; max-height: 360px; background: #0d2b16; border-radius: var(--radius);
  object-fit: cover; display: block;
}
.capture-wait { font-size: 15px; color: var(--muted); display: flex; align-items: center; gap: 8px; }
.capture-bar { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.capture-tip { margin: 0; font-size: 14px; color: var(--muted); text-align: center; }
.capture-error { display: grid; gap: 10px; justify-items: start; }
.shutter {
  width: 72px; height: 72px; border-radius: 50%; border: 4px solid #fff; background: #e5484d;
  box-shadow: 0 0 0 3px rgba(0, 0, 0, .25); cursor: pointer;
}
.shutter:disabled { opacity: .45; cursor: not-allowed; }
.shutter:not(:disabled):active { transform: scale(.94); }

/* phones: one column, bigger still */
@media (max-width: 640px) {
  body { font-size: 17.5px; }
  .chips.crops { gap: 6px; }
  .chip.crop { padding: 8px 12px; }
  .shutter { width: 76px; height: 76px; }
  .todo-list li { font-size: 17.5px; }
}
"""
    done.append("styles.css: farmer pass block")
css.write_text(s)

print(f"applied {len(done)} changes:")
for d in done:
    print("  -", d)
