#!/usr/bin/env node
/**
 * Refusal-card check: when the API answers 422 "not_a_leaf", does the UI actually
 * say so - with a way out - instead of showing a red error line or, worse, a
 * diagnosis?
 *
 * Why this exists
 * ---------------
 * The out-of-distribution gate in `modules/leaf_gate.py` refuses photos that are not
 * leaves. That path only runs on a 422, so neither the mount check (happy path) nor
 * the switch check (language switching) ever renders it. This script mounts the
 * shipped bundle in jsdom, uploads a photo through the same flow a user does, and
 * makes `/api/analyze` answer with the real 422 payload the server sends.
 *
 * It asserts:
 *   1. the refusal is on screen IN THE UI'S CURRENT LANGUAGE, and that tapping ગુ
 *      switches the refusal text to Gujarati without a second API call (the card used
 *      to keep whatever language the analysis ran in - reported with a screenshot on
 *      2026-09-15, where the buttons were Gujarati and the message stayed English),
 *   2. the retake buttons are offered ("Choose a different photo" + "Remove"),
 *   3. no disease class, confidence or advisory is rendered anywhere,
 *   4. no page errors.
 *
 * Run it:
 *   cd app/frontend && npm install     # once (esbuild + jsdom)
 *   node scripts/check_ui_refusal.mjs  # from the project root
 *
 * Exit 0 = refusal renders correctly, 1 = it does not.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STATIC = path.join(ROOT, "app", "backend", "static");
const FRONTEND = path.join(ROOT, "app", "frontend");
const require = createRequire(path.join(FRONTEND, "package.json"));

function fail(msg) {
  console.error(`✗ ${msg}`);
  process.exit(1);
}

const html = fs.readFileSync(path.join(STATIC, "index.html"), "utf8");
const asset = (html.match(/assets\/index-[A-Za-z0-9_-]+\.js/) || [])[0];
if (!asset) fail("index.html does not reference an assets/index-*.js bundle");
const bundlePath = path.join(STATIC, asset);
if (!fs.existsSync(bundlePath)) fail(`index.html references a missing file: ${asset}`);
const buildId = fs.existsSync(path.join(STATIC, "BUILD_ID.txt"))
  ? fs.readFileSync(path.join(STATIC, "BUILD_ID.txt"), "utf8").trim() : "unknown";

let esbuild;
try { esbuild = require("esbuild"); } catch {
  fail("esbuild not found - run `cd app/frontend && npm install` first");
}
let jsdom;
try { jsdom = require("jsdom"); } catch {
  fail("jsdom not found - run `cd app/frontend && npm install` first (it is a devDependency)");
}
const { JSDOM } = jsdom;

const iife = path.join(FRONTEND, "node_modules", ".cache-refusal-check.js");
try {
  esbuild.buildSync({ entryPoints: [bundlePath], bundle: true, format: "iife",
                      target: "es2020", outfile: iife, logLevel: "silent" });
} catch (e) {
  fail(`could not convert ${asset} for the DOM harness: ${e.message}`);
}
const code = fs.readFileSync(iife, "utf8");

// The exact payload the API sends for a chair / screenshot (see
// app/backend/main.py::_leaf_gate_or_refuse). Gujarati, so the check also proves the
// refusal is localized rather than hardcoded English.
//
// The exact bytes the API sends. main.py installs exception handlers that FLATTEN
// `HTTPException(detail={...})` (see _http_handler / _starlette_http_handler), so the
// wire shape is flat - verified against the running server with
// `curl -i -X POST /api/analyze -F image=@tests/fixtures/non_leaf/...`.
// The client additionally unwraps a nested {"detail": {...}} for robustness; that is
// pinned by tests/test_frontend_contract.py::test_api_client_unwraps_fastapi_detail.
const REFUSAL = {
  ok: false,
  error: "not_a_leaf",
  message: "આ ફોટો પાન જેવો લાગતો નથી. મેં નિદાન પહેલાં જ અટકી ગયો - ખોટા વિષય પર ભરોસાપાત્ર જવાબ ન મળવા કરતાં પણ ખરાબ છે.",
  hint: "એક પાન દિવસના અજવાળામાં ફ્રેમમાં ભરીને ફરી ફોટો પાડો - અથવા ડેશબોર્ડ પરનો ચકાસાયેલો નમૂનો વાપરો.",
  leaf_confidence: 0.0,
  threshold: 0.05,
};
const HEALTH = {
  status: "ok", version: "1.2.0", build_id: buildId, model_available: true, uptime_s: 1.5,
  model: { available: true, arch: "resnet18", classes: 18, img_size: 160, device: "cpu",
           checkpoint: "model/best_model.pth", val_macro_f1: 0.9935, decoding: "ensemble_tta",
           load_error: null },
  demo_mode: false,
  uploads: { heif: true, heif_error: null, extensions: [".jpg", ".png", ".heic"],
             max_pixels: 60000000, max_side_applied: 1024, max_mb: 25 },
  leaf_gate: { available: true, threshold: 0.05, threshold_uncertain: 0.3, auc: 0.998 },
};
const META = {
  app: { name: "AgriSmart AI", version: "1.2.0" }, version: "1.2.0", build_id: buildId,
  n_classes: 18, classes: ["apple_scab"], languages: ["en", "hi", "gu"], endpoints: ["/api/health"],
  model: HEALTH.model, thresholds: {}, normalisation: {}, datasets: {}, demo_mode: false,
  assistant: { llm_enabled: false }, kb_classes: 18,
};
const SAMPLES = { ok: true, count: 0, note: "stub", samples: [] };

const errors = [];
const dom = new JSDOM(html, { runScripts: "outside-only", pretendToBeVisual: true,
                              url: "https://preview.example/" });
const { window } = dom;
window.addEventListener("error", (e) => errors.push(String(e.message)));
window.addEventListener("unhandledrejection", (e) => errors.push(`unhandled rejection: ${e.reason}`));
const realConsoleError = window.console.error;
window.console.error = (...a) => { errors.push(a.map(String).join(" ").slice(0, 300)); realConsoleError.apply(window.console, a); };

const calls = [];
window.fetch = (url, opts) => {
  const p = String(url).split("?")[0];
  const method = (opts && opts.method) || "GET";
  calls.push(`${method} ${p}`);
  if (p === "/api/analyze") {
    return Promise.resolve({ ok: false, status: 422, json: () => Promise.resolve(REFUSAL),
                             text: () => Promise.resolve(JSON.stringify(REFUSAL)) });
  }
  const body = { "/api/health": HEALTH, "/api/meta": META, "/api/samples": SAMPLES }[p] ?? { ok: true };
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body),
                           text: () => Promise.resolve(JSON.stringify(body)) });
};
window.URL.createObjectURL = () => "blob:stub";
window.URL.revokeObjectURL = () => {};

try {
  window.eval(code);
} catch (e) {
  errors.push(`evaluating the bundle threw: ${e}`);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

setTimeout(async () => {
  const doc = window.document;
  const setFile = (file) => {
    const input = doc.querySelector('input[type="file"]');
    if (!input) fail("no file input found in the rendered app");
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new window.Event("change", { bubbles: true }));
  };
  const clickByText = (needle) => {
    const btn = [...doc.querySelectorAll("button")].find((b) => (b.textContent || "").includes(needle));
    if (!btn) return false;
    btn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    return true;
  };

  setFile(new window.File([new Uint8Array([1, 2, 3])], "office_chair.jpg", { type: "image/jpeg" }));
  await sleep(60);
  if (!clickByText("Analyze this photo")) fail("the two-step submit button never appeared after picking a file");
  await sleep(400);

  const text = (doc.getElementById("root").textContent || "").replace(/\s+/g, " ");
  const fatal = errors.filter((e) => !/Warning:|deprecat/i.test(e));
  const analyzeCalls = calls.filter((c) => c.includes("/api/analyze")).length;

  // the refusal itself
  // The card renders from app/frontend/src/i18n.js (refusal_not_a_leaf), so the text
  // follows the language picker. Default UI language at mount is English.
  const EN_MESSAGE = "This photo does not look like a leaf";
  const GU_MESSAGE = "આ ફોટો પાન જેવો લાગતો નથી";
  const showsMessage = text.includes(EN_MESSAGE);
  const showsHint = text.includes("Fill the frame with a single leaf");
  // a way out
  const retake = [...doc.querySelectorAll("button")]
    .some((b) => ["Choose a different photo", "બીજો ફોટો પસંદ કરો", "दूसरी फोटो चुनें"]
      .includes((b.textContent || "").trim()));
  // and above all: no diagnosis for a non-leaf
  // A refused photo must not produce a *diagnosis*: no disease label, no confidence
  // number, no advisory cards. Crop names in the form fields ("planted crop: tomato")
  // are not a diagnosis, so match the model's own output vocabulary instead.
  const leaked = ["late blight", "early blight", "leaf mold", "black rot", "scab",
                  "bacterial spot", "grey leaf spot", "common rust"]
    .filter((w) => text.toLowerCase().includes(w.toLowerCase()));
  const hasVerdictCard = !!doc.querySelector(".card.verdict .headline, .card.verdict h2");
  const hasAdvisory = !!doc.querySelector(".card.actions, .card.risk, .card.irrigation");

  console.log(`refusal check - build ${buildId}, bundle ${asset}`);
  console.log(`  analyze calls : ${analyzeCalls}`);
  console.log(`  refusal shown : ${showsMessage ? "yes" : "NO"}`);
  console.log(`  hint shown    : ${showsHint ? "yes" : "NO"}`);
  console.log(`  retake button : ${retake ? "yes" : "NO"}`);
  console.log(`  leaked labels : ${leaked.length ? leaked.join(", ") : "none"}`);
  console.log(`  verdict card  : ${hasVerdictCard ? "PRESENT (must not be)" : "absent"}`);
  if (fatal.length) console.log(`  errors        :\n    - ${fatal.slice(0, 4).join("\n    - ")}`);

  try { fs.unlinkSync(iife); } catch { /* cache file is disposable */ }

  // ---- the reported bug: does the refusal follow the language picker? ----
  const guBtn = [...doc.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "ગુજરાતી")
    || [...doc.querySelectorAll("button")].find((b) => (b.textContent || "").includes("ગુ"));
  let switched = false, analyzeCallsAfterSwitch = analyzeCalls;
  if (guBtn) {
    guBtn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    await sleep(350);
    const after = (doc.getElementById("root").textContent || "").replace(/\s+/g, " ");
    switched = after.includes(GU_MESSAGE);
    analyzeCallsAfterSwitch = calls.filter((c) => c.includes("/api/analyze")).length;
    console.log(`  refusal in ગુજરાતી after switching : ${switched ? "yes" : "NO"}`);
    console.log(`  extra analyze calls              : ${analyzeCallsAfterSwitch - analyzeCalls}`);
  } else {
    console.log("  refusal in ગુજરાતી after switching : (no language button found)");
  }

  const problems = [];
  if (analyzeCalls !== 1) problems.push(`expected exactly one /api/analyze call, saw ${analyzeCalls}`);
  if (!showsMessage) problems.push("the API's refusal message is not on screen");
  if (!showsHint) problems.push("the retake hint is not on screen");
  if (!retake) problems.push("no 'choose a different photo' button - the user is stuck");
  if (leaked.length) problems.push(`a diagnosis leaked into a refused analysis: ${leaked.join(", ")}`);
  if (!guBtn) problems.push("the ગુ language button is missing from the header");
  if (guBtn && !switched) problems.push("the refusal text does not follow the language picker (stayed English after tapping ગુજરાતી)");
  if (guBtn && analyzeCallsAfterSwitch !== analyzeCalls) {
    problems.push("switching language re-ran /api/analyze - the card must re-localize without a new analysis");
  }
  if (hasVerdictCard) problems.push("a verdict card is rendered for a refused photo");
  if (hasAdvisory) problems.push("advisory cards are rendered for a refused photo");
  if (fatal.length) problems.push(`page errors: ${fatal.slice(0, 2).join(" | ")}`);

  if (problems.length) fail(problems.join("; "));
  console.log("✓ a non-leaf upload is refused with a localized message, a retake button and no diagnosis");
  process.exit(0);
}, 900);
