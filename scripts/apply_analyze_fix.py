#!/usr/bin/env python3
"""Re-apply the "error on analysing part" fixes to a reverted tree (idempotent).

The sandbox silently reverts app/frontend/src/App.jsx, api.js, i18n.js and styles.css
to the pre-farmer snapshot (recycles #5, #6, #7...). The backend gate fixes are already
covered by scripts/apply_backend_gate.py; this script covers the frontend half of the
analyse path, so `bash scripts/rebuild_after_revert.sh` brings the whole thing back.

What it guarantees
------------------
1. app/frontend/src/fields.mjs exists        - optional-field sanitiser (a typo in soil
   pH / weather boxes must never block a diagnosis with a 422).
2. api.js unwraps FastAPI's nested {"detail": {...}} payload.
3. i18n.js carries the `analysis_problem` phrase in EN/HI/GU.
4. App.jsx imports + uses the sanitiser, and never leaves the farmer with a silent
   button when a response is neither a diagnosis nor an explicit error.
5. The regression tests that pin 1-4 exist (test_leaf_gate.py, test_frontend_contract.py).

Run:  python3 scripts/apply_analyze_fix.py         (0 changes when already applied)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "app" / "frontend" / "src"
changes: list[str] = []
problems: list[str] = []


def note(msg: str) -> None:
    changes.append(msg)
    print(f"   + {msg}")


def warn(msg: str) -> None:
    problems.append(msg)
    print(f"   ! {msg}")


# --------------------------------------------------------------------------- 1. fields.mjs
FIELDS_MJS = '''// Optional dashboard fields - normalised before they are sent to /api/analyze.
//
// Why this exists
// ---------------
// Every soil/weather field is optional context for the photo diagnosis, but the
// server rejects the whole request with 422 "invalid_request" when a value does not
// parse as a number ("7,5" - a comma decimal, what most phone keyboards offer - or
// "NA", or a trailing unit like "12 cm") or when it falls outside a hard range. The
// farmer then sees a red error and no diagnosis even though the photo was fine.
// That is the "error on analysing part" reported on 2026-09-15.
//
// Rule: a typo in an optional field must never block the leaf diagnosis. We send
// only values the server accepts, and mirror the cleaned values back into the form
// so the screen shows exactly what was sent.
//
// Pure module (no DOM, no React) so both the bundle and scripts/check_ui_fields.mjs
// can use the same code.

/** Hard server-side ranges (app/backend/main.py::analyze_endpoint). Outside -> drop. */
export const RANGE_FIELDS = {
  soil_moisture_pct: [0, 100],
  soil_ph: [0, 14],
};

/** Numbers the server accepts as any finite float - only the type is checked. */
export const TYPE_ONLY_FIELDS = [
  'area_ha', 'nitrogen', 'phosphorus', 'potassium', 'temperature', 'humidity', 'rainfall',
];

/**
 * Parse one form value the way a person would write it.
 * @returns {number|null|NaN} a finite number, null for "left blank", NaN for unusable.
 */
export function parseNumber(raw) {
  const text = String(raw ?? '').trim().replace(/,/g, '.').replace(/\\s+/g, '');
  if (text === '') return null;
  // Tolerate a trailing unit ("12cm", "45 %") - the digits are what the farmer meant.
  const match = text.match(/^-?\\d*\\.?\\d+/);
  if (!match) return NaN;
  const n = Number(match[0]);
  return Number.isFinite(n) ? n : NaN;
}

/** `use_sensors` must reach FastAPI as a real boolean, never as the string "maybe". */
export function parseBool(raw, fallback = true) {
  if (typeof raw === 'boolean') return raw;
  const text = String(raw ?? '').trim().toLowerCase();
  if (['true', '1', 'yes', 'on'].includes(text)) return true;
  if (['false', '0', 'no', 'off'].includes(text)) return false;
  return fallback;
}

/**
 * Clean every optional numeric field of an /api/analyze form.
 * @param {object} form raw form state
 * @returns {{values: object, dropped: string[]}} values to send ('' = omit) + what was ignored
 */
export function cleanNumericFields(form = {}) {
  const values = { ...form };
  const dropped = [];

  const handle = (key, range) => {
    const parsed = parseNumber(form[key]);
    if (parsed === null) { values[key] = ''; return; }          // blank stays blank
    if (Number.isNaN(parsed)) { values[key] = ''; dropped.push(key); return; }
    if (range && (parsed < range[0] || parsed > range[1])) { values[key] = ''; dropped.push(key); return; }
    values[key] = parsed;
  };

  for (const [key, range] of Object.entries(RANGE_FIELDS)) handle(key, range);
  for (const key of TYPE_ONLY_FIELDS) handle(key, null);

  values.use_sensors = parseBool(form.use_sensors, true);
  return { values, dropped };
}
'''

fields_path = FRONT / "fields.mjs"
if not fields_path.is_file() or "cleanNumericFields" not in fields_path.read_text():
    fields_path.write_text(FIELDS_MJS)
    note("app/frontend/src/fields.mjs written (optional-field sanitiser)")

# --------------------------------------------------------------------------- 2. api.js
api_path = FRONT / "api.js"
api_src = api_path.read_text() if api_path.is_file() else ""
if "body.detail" not in api_src:
    old = """  if (!res.ok && body && !body.message) body.message = `Request failed (${res.status})`
  return body
}"""
    new = """  // FastAPI wraps HTTPException payloads as {"detail": {...}} (pydantic validation
  // errors arrive as {"detail": [...]}). Hoist the object form so every caller sees
  // one flat shape - ok / error / message / hint / details - whether the server
  // answered 200 or 4xx. Without this the friendly "not a leaf" refusal (422) loses
  // its ok:false flag and the UI silently does nothing instead of explaining.
  if (body && body.detail && typeof body.detail === 'object' && !Array.isArray(body.detail)) {
    body = { ...body.detail }
  }
  if (!res.ok && body && !body.message) body.message = `Request failed (${res.status})`
  return body
}"""
    if old in api_src:
        api_path.write_text(api_src.replace(old, new, 1))
        note("api.js unwraps FastAPI's nested detail payload")
    else:
        warn("api.js: could not find the json helper to patch - check it by hand")
else:
    print("   = api.js already unwraps detail")

# --------------------------------------------------------------------------- 3. i18n.js
i18n_path = FRONT / "i18n.js"
i18n_src = i18n_path.read_text() if i18n_path.is_file() else ""
if "analysis_problem" not in i18n_src:
    anchor = "  analyzing: {"
    idx = i18n_src.find(anchor)
    if idx == -1:
        warn("i18n.js: no `analyzing:` key to anchor on")
    else:
        end = i18n_src.index("\n", idx) + 1
        block = """  analysis_problem: {
    en: 'The analysis did not come back — please try again.',
    hi: 'विश्लेषण पूरा नहीं हो सका — कृपया दोबारा कोशिश करें।',
    gu: 'વિશ્લેષણ પૂરું થઈ શક્યું નથી — ફરી પ્રયાસ કરો.',
  },
"""
        i18n_path.write_text(i18n_src[:end] + block + i18n_src[end:])
        note("i18n.js carries `analysis_problem` in EN/HI/GU")
else:
    print("   = i18n.js already has analysis_problem")

# --------------------------------------------------------------------------- 4. App.jsx
app_path = FRONT / "App.jsx"
app_src = app_path.read_text() if app_path.is_file() else ""
if "cleanNumericFields" not in app_src:
    if "import * as api from './api.js'" not in app_src:
        warn("App.jsx: api import missing - is this the farmer-UI version?")
    else:
        app_src = app_src.replace("import * as api from './api.js'",
                                  "import * as api from './api.js'\nimport { cleanNumericFields } from './fields.mjs'", 1)

        old_fields = re.search(
            r"    const fields = \{\n      language: lang,\n      sample_id: sampleId,\n(?:.*\n)*?    \}",
            app_src)
        if old_fields is None:
            warn("App.jsx: the analyse `fields` block was not found - patch by hand")
        else:
            new_fields = """    // Optional fields are normalised first: a comma decimal ("7,5"), a stray unit
    // ("12 cm") or an out-of-range number used to make the server answer 422 and the
    // farmer saw an error instead of a diagnosis for a perfectly good photo. Only
    // values the API accepts are sent, and the form is updated to match.
    const { values: clean, dropped } = cleanNumericFields(form)
    if (dropped.length) setForm(clean)
    const fields = {
      language: lang,
      sample_id: sampleId,
      soil_moisture_pct: clean.soil_moisture_pct,
      soil_ph: clean.soil_ph,
      city: form.city,
      planted_crop: form.planted_crop,
      area_ha: clean.area_ha,
      nitrogen: clean.nitrogen, phosphorus: clean.phosphorus, potassium: clean.potassium,
      temperature: clean.temperature, humidity: clean.humidity, rainfall: clean.rainfall,
      use_sensors: clean.use_sensors,
    }"""
            app_src = app_src[:old_fields.start()] + new_fields + app_src[old_fields.end():]
            note("App.jsx normalises the optional fields before POSTing")

        old_tail = """      if (res.session_id) {
        setAnalysis(res)
        setChat([])
        setView('results')
        scrollTop()
      }"""
        new_tail = """      if (res.session_id) {
        setAnalysis(res)
        setChat([])
        setView('results')
        scrollTop()
      } else if (res.ok !== false) {
        // A response that is neither a diagnosis nor an explicit error would leave the
        // farmer staring at a spinner that stopped for no visible reason. Say something.
        setNotice(null)
        setError(res.message || t('analysis_problem'))
        scrollTop()
      }"""
        if old_tail in app_src:
            app_src = app_src.replace(old_tail, new_tail, 1)
            note("App.jsx never fails silently after an analyse call")
        else:
            warn("App.jsx: the session_id tail was not found - patch by hand")

        app_path.write_text(app_src)
else:
    print("   = App.jsx already uses the normaliser")

# ------------------------------------------------- 4b. refusal card follows the UI language
# The refusal card used to render whatever text the server returned for the language
# that was active AT ANALYSIS TIME. Switching to Hindi/Gujarati afterwards left the
# message and hint in English while the buttons translated (reported with a screenshot
# on 2026-09-15). The card now renders from the client's own i18n keys, so it follows
# the language picker live, exactly like every other server-provided string.
i18n_src = i18n_path.read_text() if i18n_path.is_file() else ""
if "refusal_not_a_leaf" not in i18n_src:
    anchor_i18n = "  analyzing: {"
    idx = i18n_src.find(anchor_i18n)
    if idx == -1:
        warn("i18n.js: no `analyzing:` key to anchor the refusal strings on")
    else:
        end = i18n_src.index("\n", idx) + 1
        keys = """  refusal_not_a_leaf: {
    en: 'This photo does not look like a leaf. I stopped before diagnosing anything - a confident answer about the wrong subject is worse than no answer.',
    hi: 'यह फोटो पत्ती की नहीं लगती। मैंने निदान से पहले ही रुक गया - गलत विषय पर भरोसेमंद उत्तर न मिलने से भी बुरा है।',
    gu: 'આ ફોટો પાન જેવો લાગતો નથી. મેં નિદાન પહેલાં જ અટકી ગયો - ખોટા વિષય પર ભરોસાપાત્ર જવાબ ન મળવા કરતાં પણ ખરાબ છે.',
  },
  refusal_not_a_leaf_hint: {
    en: 'Fill the frame with a single leaf in daylight, then upload again - or tap one of the verified sample photos on the dashboard to see a full analysis.',
    hi: 'दिन की रोशनी में एक ही पत्ती फ्रेम में भरें, फिर दोबारा अपलोड करें - या डैशबोर्ड पर दिए प्रमाणित नमूना फोटो में से कोई चुनें।',
    gu: 'દિવસના અજવાળામાં એક જ પાન ફ્રેમમાં ભરો, પછી ફરી અપલોડ કરો - અથવા ડેશબોર્ડ પરના ચકાસાયેલા નમૂના ફોટામાંથી એક પસંદ કરો.',
  },
"""
        i18n_path.write_text(i18n_src[:end] + keys + i18n_src[end:])
        note("i18n.js carries the refusal card strings in EN/HI/GU")

app_path = FRONT / "App.jsx"
app_src = app_path.read_text() if app_path.is_file() else ""
if app_src and "not_a_leaf'" not in app_src.split("setNotice")[0][-400:] and "notice.code" not in app_src:
    # 1. remember the error code so the card can pick its own strings
    if "setNotice({ message: msg, hint: res.hint })" in app_src:
        app_src = app_src.replace("setNotice({ message: msg, hint: res.hint })",
                                  "setNotice({ code: res.error, message: msg, hint: res.hint })", 1)
        note("App.jsx remembers the refusal code")
    # 2. render the card from the live language instead of the analysis-time text
    old_card = """                  <b>{notice.message}</b>
                  {notice.hint && <p className="muted small tight">{notice.hint}</p>}"""
    new_card = """                  {notice.code === 'not_a_leaf' ? (
                    <>
                      <b>{t('refusal_not_a_leaf')}</b>
                      <p className="muted small tight">{t('refusal_not_a_leaf_hint')}</p>
                    </>
                  ) : (
                    <>
                      <b>{notice.message}</b>
                      {notice.hint && <p className="muted small tight">{notice.hint}</p>}
                    </>
                  )}"""
    if old_card in app_src:
        app_src = app_src.replace(old_card, new_card, 1)
        note("the refusal card follows the language picker (message + hint)")
        app_path.write_text(app_src)
    elif "refusal_not_a_leaf" in app_src:
        print("   = refusal card already language-aware")
    else:
        warn("App.jsx: the refusal card markup was not found - check the farmer pass ran first")

# --------------------------------------------------------------------------- 5. tests
lg = ROOT / "tests" / "test_leaf_gate.py"
lg_src = lg.read_text() if lg.is_file() else ""
if "test_refusal_body_is_flat_on_the_wire" not in lg_src:
    anchor = "    def test_non_leaf_upload_is_a_422_not_a_diagnosis(self, client):"
    block = '''    def test_refusal_body_is_flat_on_the_wire(self, client):
        """Contract lock: the 4xx body is flat, and the browser reads it that way.

        main.py installs exception handlers that return `exc.detail` directly, so both
        the refusal (not_a_leaf) and validation errors arrive flat - verified against
        the running server. The UI shows the refusal card by reading `body.ok === false`
        and `body.error === "not_a_leaf"` at the top level (app/frontend/src/App.jsx);
        scripts/check_ui_refusal.mjs stubs this same shape. If a handler is ever removed
        so FastAPI's default {"detail": {...}} wrapper returns, the farmer sees a dead
        button - which is exactly what this test is here to catch.
        """
        path = sorted(FIXTURES.iterdir())[0]
        res = self._post(client, path)
        assert res.status_code == 422
        body = res.json()
        assert "detail" not in body, f"the browser expects a flat body, got {body}"
        assert body["ok"] is False
        assert body["error"] == "not_a_leaf"
        assert body["message"] and body["hint"]

'''
    if anchor in lg_src:
        lg.write_text(lg_src.replace(anchor, block + anchor, 1))
        note("tests/test_leaf_gate.py pins the flat refusal body")
    else:
        warn("test_leaf_gate.py: anchor missing")

fc = ROOT / "tests" / "test_frontend_contract.py"
fc_src = fc.read_text() if fc.is_file() else ""
if "test_api_client_unwraps_fastapi_detail" not in fc_src:
    fc_src += '''

def test_api_client_unwraps_fastapi_detail():
    """The client must hoist {"detail": {...}} so ok/error/message/hint are readable."""
    src = (ROOT / "app" / "frontend" / "src" / "api.js").read_text()
    assert "body.detail" in src, "api.js must unwrap FastAPI's nested detail payload"
    assert "!Array.isArray(body.detail)" in src, (
        "pydantic validation errors send detail as a list - it must not be spread"
    )
    note = "ok"
'''
    note("tests/test_frontend_contract.py pins the client unwrap")

if "TestOptionalFieldsCannotBlockADiagnosis" not in fc_src:
    anchor = "class TestShippedBundleMounts:"
    block = '''class TestOptionalFieldsCannotBlockADiagnosis:
    """A typo in a soil/weather box must never stop the leaf diagnosis.

    Regression (2026-09-15, the "error on analysing part"): every dashboard field is
    optional context, but FastAPI parses them as floats and the endpoint 422s on
    out-of-range soil values. Typing "7,5" or "NA" therefore killed the whole
    analysis and the farmer saw "Some values are missing or out of range" instead of
    a diagnosis for a perfectly good photo. app/frontend/src/fields.mjs now
    normalises those values client-side; scripts/check_ui_fields.mjs proves the rule
    and this test keeps it wired in.
    """

    def test_a_typo_in_an_optional_field_does_not_block_the_analysis(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if node is None:
            pytest.skip("node not installed - cannot exercise the normaliser")
        proc = subprocess.run([node, "scripts/check_ui_fields.mjs"], cwd=ROOT,
                              capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, (
            "an optional-field typo can block a diagnosis again:\\n"
            f"{proc.stdout}\\n{proc.stderr[-2000:]}"
        )

    def test_a_bad_number_cannot_block_the_shipped_bundle(self):
        """End-to-end: type an out-of-range soil pH into the real bundle, click
        Analyse, and inspect the FormData that fetch receives. Verified to fail
        against the pre-fix behaviour (see HANDOFF.md 5.1b)."""
        import shutil
        import subprocess
        node = shutil.which("node")
        if node is None:
            pytest.skip("node not installed - cannot mount the UI")
        for dep in ("esbuild", "jsdom"):
            if not (ROOT / "app" / "frontend" / "node_modules" / dep).is_dir():
                pytest.skip(f"{dep} missing - run `cd app/frontend && npm install` to enable this check")
        proc = subprocess.run([node, "scripts/check_ui_analyze_payload.mjs"], cwd=ROOT,
                              capture_output=True, text=True, timeout=300)
        assert proc.returncode == 0, (
            "an optional-field typo blocks the analysis again:\\n"
            f"{proc.stdout}\\n{proc.stderr[-2000:]}"
        )

    def test_the_shipped_bundle_uses_the_normaliser(self):
        src = (ROOT / "app" / "frontend" / "src" / "App.jsx").read_text()
        assert "cleanNumericFields" in src, (
            "App.jsx must normalise the optional fields before POSTing to /api/analyze"
        )
        assert (ROOT / "app" / "frontend" / "src" / "fields.mjs").is_file()


'''
    if anchor in fc_src:
        fc.write_text(fc_src.replace(anchor, block + anchor, 1))
        note("tests/test_frontend_contract.py pins the sanitiser end to end")
    else:
        fc.write_text(fc_src)
        warn("test_frontend_contract.py: mount class anchor missing")

# --------------------------------------------------------------------------- report
print(f"\napply_analyze_fix: {len(changes)} change(s)"
      + (f", {len(problems)} problem(s)" if problems else " (or already applied)"))
if problems:
    for p in problems:
        print(f"   ! {p}")
    sys.exit(1)
