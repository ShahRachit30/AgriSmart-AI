#!/usr/bin/env node
/**
 * Analyse-payload check: can a bad number in an optional box block the diagnosis?
 *
 * Why this exists
 * ---------------
 * The "error on analysing part" (reported 2026-09-15): every soil/weather field on
 * the analyse card is optional context, but the API parses them as floats and the
 * endpoint hard-rejects out-of-range soil values with 422. `<input type="number">`
 * min/max attributes do NOT stop someone typing 999 into soil pH, so the whole
 * photo analysis failed with "soil_ph must be between 0 and 14" - a red error
 * instead of a diagnosis for a perfectly good leaf.
 *
 * This mounts the SHIPPED bundle in jsdom, types an out-of-range value, clicks
 * Analyse and inspects the real FormData that fetch receives. It fails if the value
 * still goes out on the wire.
 *
 * Run:  node scripts/check_ui_analyze_payload.mjs    (exit 0 = safe, 1 = blocked)
 */
import fs from "node:fs";
import { createRequire } from "node:module";

import path from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STATIC = path.join(ROOT, "app", "backend", "static");
const FRONTEND = path.join(ROOT, "app", "frontend");
const require = createRequire(path.join(FRONTEND, "package.json"));
const esbuild = require("esbuild");
const { JSDOM } = require("jsdom");

const html = fs.readFileSync(path.join(STATIC, "index.html"), "utf8");
const asset = html.match(/assets\/index-[A-Za-z0-9_-]+\.js/)[0];
const iife = path.join(FRONTEND, "node_modules", ".probe-payload.js");
esbuild.buildSync({ entryPoints: [path.join(STATIC, asset)], bundle: true, format: "iife",
                    target: "es2020", outfile: iife, logLevel: "silent" });
const code = fs.readFileSync(iife, "utf8");

const HEALTH = { status: "ok", version: "1.2.0", model_available: true, uptime_s: 1,
  model: { available: true, arch: "resnet18", classes: 18, img_size: 160, device: "cpu" },
  demo_mode: false, uploads: { heif: true, extensions: [".jpg"], max_pixels: 1e8, max_mb: 25 },
  leaf_gate: { available: true, threshold: 0.05, threshold_uncertain: 0.3, auc: 0.998 } };
const OK = { session_id: "probe", language: "en", generated_at: "now",
  prediction: { class: "grape_black_rot", crop: "Grape", condition: "Black Rot", healthy: false,
    confidence: 0.9, top3: [], margin: 0.5, img_size: 160, model_name: "resnet18", inference_ms: 50,
    leaf_check: { p_leaf: 0.99, verdict: "leaf", threshold: 0.05 } },
  risk: {}, irrigation: {}, recommendations: {}, actions: [], };

let sent = null;
const dom = new JSDOM(html, { runScripts: "outside-only", pretendToBeVisual: true,
                              url: "https://preview.example/" });
const { window } = dom;
window.fetch = (url, opts) => {
  const p = String(url).split("?")[0];
  if (p === "/api/analyze") {
    sent = opts && opts.body;                       // the FormData the browser would send
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(OK),
                             text: () => Promise.resolve(JSON.stringify(OK)) });
  }
  const body = { "/api/health": HEALTH, "/api/meta": { app: { version: "1.2.0" }, version: "1.2.0",
      classes: ["x"], languages: ["en"], model: HEALTH.model, assistant: {}, endpoints: [] },
    "/api/samples": { ok: true, count: 0, samples: [] } }[p] ?? { ok: true };
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body),
                           text: () => Promise.resolve(JSON.stringify(body)) });
};
window.URL.createObjectURL = () => "blob:probe";
window.URL.revokeObjectURL = () => {};
window.eval(code);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await sleep(300);
const doc = window.document;
const findByLabel = (re) => [...doc.querySelectorAll("input")].find((i) => {
  const ctx = (i.closest("label")?.textContent || "") + (i.getAttribute("aria-label") || "") +
              (i.getAttribute("placeholder") || "") + (i.getAttribute("name") || "");
  return re.test(ctx);
});
const ph = findByLabel(/soil\s*ph|pH/i);
if (!ph) { console.error("✗ could not find a soil pH input"); process.exit(1); }
// type the way a phone keyboard would: comma decimal
const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
setter.call(ph, "999");   // out of range 0-14: min/max attrs do not stop typing
ph.dispatchEvent(new window.Event("input", { bubbles: true }));
await sleep(80);

const input = doc.querySelector('input[type="file"]');
Object.defineProperty(input, "files", { value: [new window.File([new Uint8Array([1,2,3])], "leaf.jpg", { type: "image/jpeg" })], configurable: true });
input.dispatchEvent(new window.Event("change", { bubbles: true }));
await sleep(80);
const btn = [...doc.querySelectorAll("button")].find((b) => (b.textContent || "").includes("Analyze this photo"));
if (!btn) { console.error("✗ two-step submit button missing"); process.exit(1); }
btn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(400);

try { fs.unlinkSync(iife); } catch {}
if (!sent) { console.error("✗ /api/analyze was never called"); process.exit(1); }
const get = (k) => (typeof sent.get === "function" ? sent.get(k) : "(no get)");
console.log(`typed soil_ph = "999" (out of range) -> sent soil_ph = ${JSON.stringify(get("soil_ph"))}`);
console.log(`sent language = ${JSON.stringify(get("language"))} | image attached: ${sent.get("image") ? "yes" : "NO"}`);
const good = get("soil_ph") === null || get("soil_ph") === "";
console.log(good
  ? "✓ the shipped bundle drops the out-of-range value - the analysis is not blocked"
  : "✗ the bundle still sends the out-of-range value (the server answers 422)");
process.exit(good ? 0 : 1);
