#!/usr/bin/env node
/**
 * Mount check: does the SHIPPED bundle actually render?
 *
 * Why this exists
 * ---------------
 * A `ReferenceError` inside a component (e.g. a handler from a parent's scope used
 * in a child's JSX) throws during React's render, React unmounts the tree, and the
 * user gets a *blank page* — while `GET /` still returns 200 and the JS file still
 * downloads fine. Grepping the source for a function name proves nothing about
 * whether it is in scope where it is used.
 *
 * This script loads the real `app/backend/static` bundle in jsdom with a stubbed
 * API and asserts the app mounted: rendered text, rendered nodes, and the API
 * calls the UI is supposed to make on first paint.
 *
 * Run it:
 *   cd app/frontend && npm install          # once (esbuild + jsdom)
 *   node scripts/check_ui_mount.mjs         # from the project root
 *
 * Exit code 0 = mounted, 1 = blank page. Also covered by
 * tests/test_frontend_contract.py::test_shipped_bundle_actually_mounts
 * (which skips when node_modules is absent).
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

// --- locate the bundle the server actually serves --------------------------- //
const html = fs.readFileSync(path.join(STATIC, "index.html"), "utf8");
const asset = (html.match(/assets\/index-[A-Za-z0-9_-]+\.js/) || [])[0];
if (!asset) fail("index.html does not reference an assets/index-*.js bundle");
const bundlePath = path.join(STATIC, asset);
if (!fs.existsSync(bundlePath)) fail(`index.html references a missing file: ${asset}`);
const buildId = fs.existsSync(path.join(STATIC, "BUILD_ID.txt"))
  ? fs.readFileSync(path.join(STATIC, "BUILD_ID.txt"), "utf8").trim() : "unknown";

// --- jsdom needs a classic script, the bundle is an ES module --------------- //
let esbuild;
try {
  esbuild = require("esbuild");
} catch {
  fail("esbuild not found - run `cd app/frontend && npm install` first");
}
let jsdom;
try {
  jsdom = require("jsdom");
} catch {
  fail("jsdom not found - run `cd app/frontend && npm install` first (it is a devDependency)");
}
const { JSDOM } = jsdom;

const iife = path.join(FRONTEND, "node_modules", ".cache-mount-check.js");
try {
  esbuild.buildSync({ entryPoints: [bundlePath], bundle: true, format: "iife",
                      target: "es2020", outfile: iife, logLevel: "silent" });
} catch (e) {
  fail(`could not convert ${asset} for the DOM harness: ${e.message}`);
}
const code = fs.readFileSync(iife, "utf8");

// --- canned API answers (shape taken from the live /api/* responses) -------- //
const HEALTH = {
  status: "ok", version: "1.2.0", build_id: buildId, model_available: true, uptime_s: 1.5,
  model: { available: true, arch: "resnet18", classes: 18, img_size: 160, device: "cpu",
           checkpoint: "model/best_model.pth", val_macro_f1: 0.9935, decoding: "ensemble_tta", load_error: null },
  demo_mode: false,
  uploads: { heif: true, heif_error: null, extensions: [".jpg", ".png", ".heic"],
             max_pixels: 60000000, max_side_applied: 1024, max_mb: 25 },
};
const META = {
  app: { name: "AgriSmart AI", version: "1.2.0" }, version: "1.2.0", build_id: buildId,
  n_classes: 18, classes: ["apple_scab", "tomato_late_blight"], languages: ["en", "hi", "gu"],
  endpoints: ["/api/health", "/api/analyze"], model: HEALTH.model, thresholds: {}, normalisation: {},
  datasets: { train: "PlantVillage", test: "PlantDoc" }, assistant: { llm_enabled: false },
  kb_classes: 18, demo_mode: false, uploads: HEALTH.uploads,
};
const SAMPLES = {
  ok: true, count: 2,
  note: "Scored with the deployed decoding on PlantDoc field photos - these are real field images.",
  samples: [
    { id: "apple_healthy__x", kind: "right", true_class: "apple_healthy", model_says: "apple_healthy",
      confidence: 0.98, image_url: "/api/samples/apple_healthy__x/image" },
    { id: "tomato_early_blight__y", kind: "hard", true_class: "tomato_late_blight", model_says: "tomato_early_blight",
      confidence: 0.71, image_url: "/api/samples/tomato_early_blight__y/image" },
  ],
};

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
  calls.push(`${(opts && opts.method) || "GET"} ${p}`);
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

setTimeout(() => {
  const root = window.document.getElementById("root");
  const text = (root && root.textContent ? root.textContent : "").replace(/\s+/g, " ").trim();
  const nodes = root ? root.querySelectorAll("*").length : 0;
  const fatal = errors.filter((e) => !/Warning:|deprecat/i.test(e));

  console.log(`mount check - build ${buildId}, bundle ${asset}`);
  console.log(`  rendered text : ${text.length} chars`);
  console.log(`  rendered nodes: ${nodes}`);
  console.log(`  API calls     : ${calls.length ? calls.join(", ") : "NONE (never mounted)"}`);
  if (fatal.length) console.log(`  errors        :\n    - ${fatal.slice(0, 4).join("\n    - ")}`);
  console.log(`  first words   : "${text.slice(0, 120)}"`);

  try { fs.unlinkSync(iife); } catch { /* cache file is disposable */ }

  if (fatal.length) fail("the shipped UI threw during mount -> BLANK PAGE");
  if (nodes < 20) fail(`the UI rendered only ${nodes} nodes - looks blank`);
  if (!/GET \/api\/health/.test(calls.join("\n"))) fail("the UI never called /api/health - did it mount?");
  console.log("✓ the shipped bundle renders");
  process.exit(0);
}, 1500);
