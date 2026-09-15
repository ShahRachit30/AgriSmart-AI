#!/usr/bin/env node
/**
 * Language-switch check: does tapping हि / ગુ actually change the WHOLE UI?
 *
 * Why this exists
 * ---------------
 * The requirement is that switching the language re-renders the entire interface
 * *and* all server-provided content (analysis, samples, sensors, metrics) in the
 * chosen language. That is easy to break silently: one `useAsync` that forgets the
 * language in its dependency list, one card that keeps a hardcoded English label,
 * one request that forgets `?language=`.
 *
 * This script drives the real shipped bundle in jsdom:
 *   1. mount           -> English
 *   2. click a sample  -> POST /api/analyze ... and the results render
 *   3. click ગુ         -> every string on screen must be Gujarati, the reads must
 *                         be refetched with language=gu, and the analysis must be
 *                         re-rendered through POST /api/relocalize (same numbers,
 *                         new words - the model is NOT run again)
 *
 * The stubbed API answers echo the requested language back (NODE-gu, COND-gu, ...)
 * so the assertions can tell which language each piece of content came from.
 *
 * Run:  node scripts/check_ui_switch.mjs        (needs app/frontend/node_modules)
 * Exit: 0 = switch is complete, 1 = something stayed in the old language.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STATIC = path.join(ROOT, "app", "backend", "static");
const FRONTEND = path.join(ROOT, "app", "frontend");
const require = createRequire(path.join(FRONTEND, "package.json"));

const problems = [];
const note = (msg) => problems.push(msg);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let esbuild, jsdom;
try { esbuild = require("esbuild"); } catch { console.error("✗ esbuild missing - cd app/frontend && npm install"); process.exit(1); }
try { jsdom = require("jsdom"); } catch { console.error("✗ jsdom missing - cd app/frontend && npm install"); process.exit(1); }
const { JSDOM } = jsdom;

// --- the bundle the server actually serves ---------------------------------- //
const html = fs.readFileSync(path.join(STATIC, "index.html"), "utf8");
const asset = (html.match(/assets\/index-[A-Za-z0-9_-]+\.js/) || [])[0];
if (!asset) { console.error("✗ index.html has no bundle reference"); process.exit(1); }
const bundlePath = path.join(STATIC, asset);
if (!fs.existsSync(bundlePath)) { console.error(`✗ missing ${asset}`); process.exit(1); }
const buildId = fs.existsSync(path.join(STATIC, "BUILD_ID.txt"))
  ? fs.readFileSync(path.join(STATIC, "BUILD_ID.txt"), "utf8").trim() : "unknown";

const iife = path.join(FRONTEND, "node_modules", ".cache-switch-check.js");
try {
  esbuild.buildSync({ entryPoints: [bundlePath], bundle: true, format: "iife",
                      target: "es2020", outfile: iife, logLevel: "silent" });
} catch (e) { console.error(`✗ bundle conversion failed: ${e.message}`); process.exit(1); }
const code = fs.readFileSync(iife, "utf8");

// --- canned API answers, language-aware ------------------------------------- //
const langOf = (url) => (String(url).match(/[?&]language=([a-z]{2})/) || [])[1] || null;
// recursively stamp the language into every {L} placeholder, so each piece of prose
// on screen can be traced back to the request that produced it
const stamp = (lang, v) => {
  if (typeof v === "string") return v.replaceAll("{L}", lang);
  if (Array.isArray(v)) return v.map((x) => stamp(lang, x));
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, stamp(lang, x)]));
  return v;
};
const L = (lang, obj) => stamp(lang, obj);

const respond = (url, lang) => {
  const p = String(url).split("?")[0];
  if (p === "/api/health") {
    return { status: "ok", build_id: buildId, model_available: true, uptime_s: 1,
             model: { available: true, arch: "resnet18", classes: 18, img_size: 160, device: "cpu",
                      checkpoint: "model/best_model.pth", decoding: "ensemble_tta", load_error: null },
             demo_mode: false, uploads: { heif: true, max_side_applied: 1024, max_mb: 25 } };
  }
  if (p === "/api/meta") {
    return { app: { name: "AgriSmart AI" }, version: "1.2.0", build_id: buildId, n_classes: 18,
             classes: ["tomato_late_blight"], languages: ["en", "hi", "gu"], endpoints: [],
             datasets: { field_test: "PlantDoc" }, kb_classes: 18, demo_mode: false };
  }
  if (p === "/api/samples") {
    return { ok: true, count: 1, language: lang, note: "SAMPLES-NOTE-{L}",
             samples: [{ id: "tomato_late_blight__x", kind: "hard", true_class: "tomato_late_blight",
                         true_class_label: "SAMPLE-LABEL-{L}", model_says: "tomato_late_blight",
                         model_says_label: "SAMPLE-LABEL-{L}", confidence: 0.71, correct: false,
                         image_url: "/api/samples/tomato_late_blight__x/image" }]
               .map((r) => L(lang, r)) };
  }
  if (p === "/api/metrics") {
    return { ok: true, available: true, language: lang,
             field_test: { macro_f1: 0.2747, accuracy: 0.2845, top3_accuracy: 0.5144, n_images: 1318, n_classes_scored: 11 },
             summary: { note: "METRICS-NOTE-{L}".replace("{L}", lang) } };
  }
  if (p === "/api/sensors/latest") {
    return L(lang, { ok: true, language: lang, device_id: "esp32-field-1", device_name: "NODE-{L}",
             soil_moisture_pct: 19.2, temperature_c: 31.4, humidity_pct: 62, soil_ph: 6.6,
             battery_pct: 88, rssi_dbm: -71, next_sample_in_s: 120, status: "healthy",
             status_label: "STATUS-{L}", needs_irrigation: true, note: "SENSOR-NOTE-{L}" });
  }
  if (p === "/api/sensors/history") {
    return L(lang, { ok: true, language: lang, samples: [
      { soil_moisture_pct: 30, temperature_c: 30 }, { soil_moisture_pct: 27, temperature_c: 31 },
      { soil_moisture_pct: 24, temperature_c: 31.5 }],
      summary: { trend: "drying", trend_label: "TREND-{L}" } });
  }
  return { ok: true };
};

// an analysis payload with a language stamp on every prose field the UI shows
const analysisFor = (lang, sessionId, confidence) => L(lang, {
  ok: true, session_id: sessionId, language: lang,
  prediction: { class: "tomato_late_blight", condition: "Tomato late blight (Phytophthora infestans)",
                condition_localized: "COND-{L}", crop: "tomato", crop_localized: "CROP-{L}",
                confidence: confidence ?? 0.91, model_name: "resnet18", img_size: 1024, inference_ms: 42,
                top3: [{ class: "tomato_late_blight", condition: "Tomato late blight", condition_localized: "COND-{L}",
                         crop: "tomato", crop_localized: "CROP-{L}", confidence: 0.91 }] },
  risk: { risk: "critical", risk_label: "RISK-{L}", crop: "tomato", condition: "Tomato late blight",
          condition_localized: "COND-{L}", confidence_band: "high", confidence_band_label: "BAND-{L}",
          advisory_level: "emergency", advisory_level_label: "ADV-{L}", severity_kb: "critical",
          severity_label: "SEV-{L}", notes: ["NOTE-{L}"], symptoms: ["SYMPTOM-{L}"], is_healthy: false },
  actions: [{ priority: "immediate", priority_label: "PRIO-{L}", kind: "organic", kind_label: "KIND-{L}",
              text: "ACTION-{L}" }],
  recommendations: { chemical_option: { product: "Copper hydroxide", dose: "2 g/litre", note: "CHEMNOTE-{L}" } },
  irrigation: { action: "IRRIGATE_NOW", action_label: "IRR-{L}", soil_moisture_pct: 19, rain_probability_pct: 10,
                water_stress: "dry", water_stress_label: "STRESS-{L}", reasons: ["IRREASON-{L}"], alerts: [] },
  weather: { ok: true, city: "Ahmedabad", country: "IN", source: "open-meteo", temperature_c: 31, humidity_pct: 62,
             wind_kph: 9, rain_today_mm: 0, weekly_rain_mm: 12, condition: "CLOUD-{L}", code: 3, daily: [] },
  sustainability: { total: 72.4, grade: "B", band: "good", band_label: "SUSBAND-{L}", weakest_area: "disease",
                    weakest_area_label: "WEAK-{L}", subscore_labels: { water: "SUBW-{L}", weather: "SUBW-{L}",
                    disease: "SUBD-{L}", resource: "SUBR-{L}" },
                    subscores: { water: 80, weather: 96, disease: 15, resource: 80 },
                    weights: { water: 0.3, weather: 0.25, disease: 0.25, resource: 0.2 },
                    formula: "ASI = 0.30*water + ...", top_tip: "TIP-{L}" },
  crop_recommendation: { top_crop: "rice", top_crop_localized: "TOPCROP-{L}", engine: "RandomForest",
                         advice: "RAADVICE-{L}", confidence_band: "high", confidence_band_label: "RABAND-{L}",
                         recommendations: [{ crop: "rice", crop_localized: "RACROP-{L}", probability: 0.8, note: "RANOTE-{L}" }] },
  sensors: null, warnings: [], narrative: "NARRATIVE-{L}", disclaimer: "DISCLAIMER-{L}",
});

// --- DOM -------------------------------------------------------------------- //
const errors = [];
const dom = new JSDOM(html, { runScripts: "outside-only", pretendToBeVisual: true, url: "https://preview.example/" });
const { window } = dom;
window.addEventListener("error", (e) => errors.push(String(e.message)));
window.addEventListener("unhandledrejection", (e) => errors.push(`unhandled rejection: ${e.reason}`));
window.console.error = () => {};
window.scrollTo = () => {}                       // jsdom does not implement scrolling
window.Element.prototype.scrollTo = () => {}      // ...not even on elements
window.URL.createObjectURL = () => "blob:stub";
window.URL.revokeObjectURL = () => {};

const calls = [];
let session = 0;
window.fetch = async (url, opts) => {
  const method = (opts && opts.method) || "GET";
  let body = null;
  try { body = opts && opts.body && typeof opts.body === "string" ? JSON.parse(opts.body) : null; } catch { /* form data */ }
  const lang = (body && body.language) || langOf(url) || "en";
  calls.push({ method, url: String(url), lang, body });
  let payload;
  if (String(url).split("?")[0] === "/api/analyze") payload = analysisFor(lang, `S${++session}`);
  else if (String(url).split("?")[0] === "/api/relocalize") payload = analysisFor(lang, body.session_id, 0.91);
  else payload = respond(url, lang);
  return { ok: true, status: 200, json: async () => payload, text: async () => JSON.stringify(payload) };
};

window.eval(code);
await sleep(900);

const text = () => (window.document.getElementById("root").textContent || "").replace(/\s+/g, " ");
/** Exact text first; the language buttons carry full names ("ગુજરાતી") and are also
 *  matched by prefix so renaming them for farmers does not break this check. */
const findButton = (label) => {
  const buttons = [...window.document.querySelectorAll("button")];
  return buttons.find((b) => (b.textContent || "").trim() === label)
    || buttons.find((b) => (b.textContent || "").trim().startsWith(label));
};
const click = (el) => el.dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));

console.log(`language-switch check - build ${buildId}, bundle ${asset}`);
if (process.env.DUMP) {
  console.log("---- after mount ----\n" + text().slice(0, 1500));
}

// --- step 1: the app mounted in English ------------------------------------- //
if (!/Check a leaf/.test(text())) note("English mount does not show the leaf-check tab");

// --- step 2: run a bundled sample so there IS an analysis on screen --------- //
const sampleBtn = [...window.document.querySelectorAll("button")]
  .find((b) => (b.title || "").startsWith("expected:"));
if (!sampleBtn) note("no sample button found - the picker did not render");
else {
  click(sampleBtn);
  await sleep(600);
  const t1 = text();
  const analyzeCall = calls.find((c) => c.url.includes("/api/analyze"));
  if (!analyzeCall) note("clicking a sample did not POST /api/analyze");
  if (analyzeCall && analyzeCall.lang !== "en") note(`analyze ran with language=${analyzeCall.lang}, expected en`);
  if (!t1.includes("NARRATIVE-en")) note("the English analysis narrative is not on screen");
  if (process.env.DUMP) console.log("---- after analyze ----\n" + t1.slice(0, 2200));
  if (!t1.includes("COND-en")) note("the English condition name is not on screen");
}

// --- step 3: switch to Gujarati --------------------------------------------- //
const guBtn = findButton("ગુ");
if (!guBtn) note("the ગુ language button is missing from the header");
else {
  click(guBtn);
  await sleep(900);
  const t2 = text();

  if (process.env.DUMP) console.log("---- after switch ----\n" + t2.slice(0, 2500));

  // 3a. static chrome is Gujarati
  for (const [label, needle] of [["tab", "પાન તપાસો"], ["results tab", "પરિણામ"],
                                 ["assistant card", "ખેડૂત સહાયક"]]) {
    if (!t2.includes(needle)) note(`after switching, the ${label} is not in Gujarati (missing "${needle}")`);
  }
  if (t2.includes("Check a leaf") && t2.includes("પાન તપાસો")) note("both English and Gujarati chrome are rendered at once");
  if (window.document.documentElement.lang !== "gu") note(`<html lang> is "${window.document.documentElement.lang}", expected "gu"`);

  // 3b. the server-backed cards were refetched in the new language
  const after = calls.filter((c) => c.lang === "gu");
  for (const p of ["/api/samples", "/api/metrics", "/api/sensors/latest", "/api/sensors/history"]) {
    if (!after.some((c) => c.url.includes(p))) note(`${p} was not refetched with language=gu`);
  }

  // 3c. the analysis was re-rendered (same session, new language) - not re-analysed
  const reloc = calls.find((c) => c.url.includes("/api/relocalize"));
  if (!reloc) note("the analysis was not re-localized (no POST /api/relocalize)");
  else if (reloc.lang !== "gu") note(`relocalize was called with language=${reloc.lang}`);
  const analyzeCalls = calls.filter((c) => c.url.includes("/api/analyze"));
  if (analyzeCalls.length !== 1) note(`the photo was re-analysed ${analyzeCalls.length} times - it must stay at 1`);

  // 3d. every piece of analysis prose came back in Gujarati
  for (const [what, needle] of [["narrative", "NARRATIVE-gu"], ["condition", "COND-gu"], ["risk label", "RISK-gu"],
                                ["band", "BAND-gu"], ["advisory level", "ADV-gu"], ["severity", "SEV-gu"],
                                ["risk note", "NOTE-gu"], ["symptom", "SYMPTOM-gu"], ["action", "ACTION-gu"],
                                ["action tag", "PRIO-gu"], ["irrigation", "IRR-gu"], ["water stress", "STRESS-gu"],
                                ["irrigation reason", "IRREASON-gu"], ["weather", "CLOUD-gu"],
                                ["sustainability", "SUSBAND-gu"], ["weakest lever", "WEAK-gu"],
                                ["subscore name", "SUBD-gu"], ["tip", "TIP-gu"], ["crop advice", "RAADVICE-gu"],
                                ["crop name", "RACROP-gu"]]) {
    if (!t2.includes(needle)) note(`after switching, the ${what} is still not localized (missing "${needle}")`);
  }
  if (/NARRATIVE-en|COND-en|RISK-en|ACTION-en|TIP-en/.test(t2)) note("English analysis text survived the switch");

  // 3e. chip questions follow the language too, and the assistant is asked in it
  if (!t2.includes("કયો રોગ છે")) note("the assistant chips are not in Gujarati");

  // 3f. the other tab is Gujarati too - and its server-backed cards show the
  //     content that came back from the language=gu refetches
  const dashBtn = findButton("પાન તપાસો");
  if (!dashBtn) note("the Gujarati leaf-check tab could not be clicked");
  else {
    click(dashBtn);
    await sleep(400);
    const t3 = text();
    for (const [label, needle] of [["upload card title", "પાનનો ફોટો"],
                                   ["field-conditions card", "ખેતરની સ્થિતિ"],
                                   ["sensor card title", "ખેતર સેન્સર"],
                                   ["node selector", "નોડ"],
                                   ["sensor device name (server)", "NODE-gu"],
                                   ["sensor note (server)", "SENSOR-NOTE-gu"],
                                   ["trend label (server)", "TREND-gu"],
                                   ["sample label (server)", "SAMPLE-LABEL-gu"],
                                   ["metrics card", "ફીલ્ડ ટેસ્ટ મેટ્રિક્સ"]]) {
      if (!t3.includes(needle)) note(`the dashboard ${label} is not in Gujarati (missing "${needle}")`);
    }
    if (/NODE-en|SENSOR-NOTE-en|SAMPLE-LABEL-en/.test(t3)) note("the dashboard still shows English server text after the switch");
  }

  // 3g. round trip: back to English. This is where a server that hands out a NEW
  //     session id on /api/relocalize shows itself - the second switch would come
  //     back as "session expired".
  const enBtn = findButton("EN");
  if (!enBtn) note("the EN button is missing");
  else {
    click(enBtn);
    await sleep(800);
    const t4 = text();
    for (const [label, needle] of [["English chrome", "Check a leaf"], ["sensor card", "Field sensors"],
                                   ["node selector", "node"]]) {
      if (!t4.includes(needle)) note(`after switching back, the ${label} did not return to English ("${needle}")`);
    }
    if (/પાન તપાસો|ખેતર સેન્સર/.test(t4)) note("Gujarati chrome survived the switch back to English");
    if (/NODE-gu|SENSOR-NOTE-gu/.test(t4)) note("Gujarati server text survived the switch back to English");
    if (!t4.includes("NODE-en")) note("the sensor card did not come back in English");
    // ...and the analysis on the Results tab is English again (we are on the
    // dashboard right now, so its text is not mounted and cannot be asserted here)
    const resultsBtn = findButton("Result & advice");
    if (!resultsBtn) note("the Result & advice tab could not be clicked after the round trip");
    else {
      click(resultsBtn);
      await sleep(500);
      const t5 = text();
      if (!t5.includes("NARRATIVE-en")) note("the analysis did not come back in English (session expired?)");
      if (!t5.includes("COND-en")) note("the condition did not come back in English");
      if (/NARRATIVE-gu|COND-gu|ACTION-gu|RISK-gu/.test(t5)) note("Gujarati analysis text survived the switch back to English");
    }
    if (process.env.DUMP) console.log("---- after round trip ----\n" + t4.slice(0, 900) + "\nCALLS: " + JSON.stringify(calls.slice(-6)));
    const reloc = calls.filter((c) => c.url.includes("/api/relocalize"));
    if (reloc.length < 2) note(`the second switch did not re-localize the analysis (${reloc.length} calls)`);
    if (reloc.some((c) => c.url.includes("/api/relocalize") && c.lang !== "gu" && c.lang !== "en"))
      note("a relocalize call used an unexpected language");
    // the analysis must NOT have been redone: the photo was sent to the model exactly once
    const analyzeCalls2 = calls.filter((c) => c.url.includes("/api/analyze"));
    if (analyzeCalls2.length !== 1) note(`the photo was analysed ${analyzeCalls2.length} times across two switches - it must stay at 1`);
  }
}

// --- verdict ---------------------------------------------------------------- //
try { fs.unlinkSync(iife); } catch { /* disposable */ }
const fatal = errors.filter((e) => !/Warning:|deprecat|not implemented/i.test(e));
console.log(`  API calls after switch (gu): ${calls.filter((c) => c.lang === "gu").map((c) => c.url.split("?")[0]).join(", ") || "none"}`);
console.log(`  analyse calls: ${calls.filter((c) => c.url.includes("/api/analyze")).length}, relocalize: ${calls.filter((c) => c.url.includes("/api/relocalize")).length}`);

if (fatal.length) { console.log(`  render errors: ${fatal.slice(0, 3).join(" | ")}`); note("the UI threw during the switch"); }
if (problems.length) {
  console.log(`✗ language switch is incomplete (${problems.length}):`);
  problems.slice(0, 12).forEach((p) => console.log(`    - ${p}`));
  process.exit(1);
}
console.log("✓ switching language re-renders the whole UI, refetches the cards and re-localizes the analysis (both directions, no re-analysis)");
process.exit(0);
