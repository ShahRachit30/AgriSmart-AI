#!/usr/bin/env node
/**
 * Model warm-up check: does the header tell the truth while the checkpoint loads?
 *
 * Why this exists
 * ---------------
 * The ResNet18 checkpoint is 42.7 MB and loads in a background thread, so for the
 * first seconds after `./run.sh` the API honestly answers `model_available: false`.
 * The header turned that into "Model not trained yet - the advisory modules still
 * work", and because the UI read /api/health exactly once, the banner stayed there
 * forever - a judge opening the page a second too early would read a lie, and the
 * "model ... ready" pill never appeared until a manual reload.
 *
 * This script mounts the real shipped bundle in jsdom against a stub API whose
 * health endpoint reports "not loaded yet" twice, then "ready":
 *   - it must ask again (a single read is the bug),
 *   - the finished header must show "ready", not the demo-mode message.
 *
 * Run:  node scripts/check_ui_warmup.mjs      (needs app/frontend/node_modules)
 * Exit: 0 = the UI recovers on its own, 1 = it is stuck on a stale health reading.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STATIC = path.join(ROOT, "app", "backend", "static");
const FRONTEND = path.join(ROOT, "app", "frontend");
const require = createRequire(path.join(FRONTEND, "package.json"));

let esbuild, jsdom;
try { esbuild = require("esbuild"); } catch { console.error("✗ esbuild missing - cd app/frontend && npm install"); process.exit(1); }
try { jsdom = require("jsdom"); } catch { console.error("✗ jsdom missing - cd app/frontend && npm install"); process.exit(1); }
const { JSDOM } = jsdom;

const html = fs.readFileSync(path.join(STATIC, "index.html"), "utf8");
const asset = (html.match(/assets\/index-[A-Za-z0-9_-]+\.js/) || [])[0];
if (!asset) { console.error("✗ index.html has no bundle reference"); process.exit(1); }
const bundlePath = path.join(STATIC, asset);
if (!fs.existsSync(bundlePath)) { console.error(`✗ missing ${asset}`); process.exit(1); }
const buildId = fs.existsSync(path.join(STATIC, "BUILD_ID.txt"))
  ? fs.readFileSync(path.join(STATIC, "BUILD_ID.txt"), "utf8").trim() : "unknown";

const iife = path.join(FRONTEND, "node_modules", ".cache-warmup-check.js");
try {
  esbuild.buildSync({ entryPoints: [bundlePath], bundle: true, format: "iife",
                      target: "es2020", outfile: iife, logLevel: "silent" });
} catch (e) { console.error(`✗ bundle conversion failed: ${e.message}`); process.exit(1); }
const code = fs.readFileSync(iife, "utf8");

// --- stub API: the model is still loading for the first two health reads ----- //
const HEALTH_WARMING = {
  status: "ok", build_id: buildId, model_available: false, uptime_s: 1,
  model: { available: false, arch: "resnet18", classes: 18, img_size: 160, device: "cpu",
           checkpoint: "model/best_model.pth", decoding: "ensemble_tta",
           load_error: null, model_name: "warming-up" },
  demo_mode: true, uploads: { heif: true, max_side_applied: 1024, max_mb: 25 },
};
const HEALTH_READY = {
  ...HEALTH_WARMING, model_available: true, demo_mode: false,
  model: { ...HEALTH_WARMING.model, available: true, model_name: "resnet18" },
};

let healthCalls = 0;
const errors = [];
const dom = new JSDOM(html, { runScripts: "outside-only", pretendToBeVisual: true,
                              url: "https://preview.example/" });
const { window } = dom;
window.addEventListener("error", (e) => errors.push(String(e.message)));
window.addEventListener("unhandledrejection", (e) => errors.push(`unhandled rejection: ${e.reason}`));
window.console.error = () => {};
window.scrollTo = () => {};
window.Element.prototype.scrollTo = () => {};
window.URL.createObjectURL = () => "blob:stub";
window.URL.revokeObjectURL = () => {};

window.fetch = (url) => {
  const p = String(url).split("?")[0];
  let body = { ok: true };
  if (p === "/api/health") {
    healthCalls += 1;
    body = healthCalls <= 2 ? HEALTH_WARMING : HEALTH_READY;
  } else if (p === "/api/meta") {
    body = { app: { name: "AgriSmart AI" }, version: "1.2.0", build_id: buildId, n_classes: 18,
             classes: ["tomato_late_blight"], languages: ["en", "hi", "gu"], endpoints: [],
             datasets: { field_test: "PlantDoc" }, assistant: { llm_enabled: false },
             kb_classes: 18, demo_mode: false, uploads: HEALTH_READY.uploads };
  } else if (p === "/api/samples") {
    body = { ok: true, count: 0, samples: [] };
  }
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body),
                           text: () => Promise.resolve(JSON.stringify(body)) });
};

try { window.eval(code); } catch (e) { errors.push(`evaluating the bundle threw: ${e}`); }

setTimeout(() => {
  const root = window.document.getElementById("root");
  const text = (root && root.textContent ? root.textContent : "").replace(/\s+/g, " ");
  try { fs.unlinkSync(iife); } catch { /* disposable cache */ }

  const problems = [];
  if (healthCalls < 3) problems.push(`/api/health was read ${healthCalls} time(s) - the UI never retried after "warming up"`);
  if (/not trained yet/i.test(text)) problems.push('the header still says "Model not trained yet" after the model reported ready');
  if (!/ready/i.test(text)) problems.push("the header never showed the ready state");

  console.log(`model warm-up check - build ${buildId}, bundle ${asset}`);
  console.log(`  /api/health reads: ${healthCalls}`);
  console.log(`  header: "${(text.match(/.{0,60}(ready|not trained yet).{0,30}/i) || [""])[0].trim()}"`);
  const fatal = errors.filter((e) => !/Warning:|deprecat/i.test(e));
  if (fatal.length) problems.push(`the UI threw: ${fatal.slice(0, 2).join(" | ")}`);
  if (problems.length) {
    problems.forEach((p) => console.log(`✗ ${p}`));
    process.exit(1);
  }
  console.log("✓ the header recovers on its own when the checkpoint finishes loading");
  process.exit(0);
}, 7000);
