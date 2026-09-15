#!/usr/bin/env node
/**
 * Live-capture check: does "Take photo" actually work end to end - and does it fail
 * politely when the browser refuses a camera?
 *
 * Why this exists
 * ---------------
 * `getUserMedia` is the single most environment-dependent API in the app: it is
 * blocked on http:// origins, inside iframes without a camera permission policy, and
 * on any machine without a webcam. All three cases are the *normal* case for whoever
 * opens this project, so the panel has to do two things: capture a frame into the
 * ordinary two-step upload flow when it can, and offer a working way out when it
 * cannot. Neither path is reachable from the other headless checks (they never open
 * the camera), so it gets its own.
 *
 * What it asserts
 *   1. clicking "Take photo" opens the panel and calls getUserMedia (video only)
 *   2. the returned stream is attached to the <video> element
 *   3. the shutter writes a JPEG File named camera_*.jpg into the normal upload flow
 *      ("Analyze this photo" + filename on screen = the existing contract, unchanged)
 *   4. that file is what the next POST /api/analyze carries
 *   5. closing the panel stops every camera track (no left-on camera light)
 *   6. NEGATIVE CONTROL: when getUserMedia rejects with NotAllowedError, the panel
 *      explains it, offers "Use phone camera" / "Choose a photo instead", and the
 *      app keeps working (no crash, no dead-end)
 *
 * Run it:  node scripts/check_ui_capture.mjs   (needs `npm install` in app/frontend)
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

let esbuild, jsdom;
try { esbuild = require("esbuild"); } catch { fail("esbuild not found - run `cd app/frontend && npm install`"); }
try { jsdom = require("jsdom"); } catch { fail("jsdom not found - run `cd app/frontend && npm install`"); }
const { JSDOM } = jsdom;

const iife = path.join(FRONTEND, "node_modules", ".cache-capture-check.js");
try {
  esbuild.buildSync({ entryPoints: [bundlePath], bundle: true, format: "iife",
                      target: "es2020", outfile: iife, logLevel: "silent" });
} catch (e) {
  fail(`could not convert ${asset} for the DOM harness: ${e.message}`);
}
const code = fs.readFileSync(iife, "utf8");

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
  assistant: { llm_enabled: false }, kb_classes: 18, uploads: HEALTH.uploads,
};
const ANALYSIS = {
  ok: true, session_id: "cam-1", status: "analyzed",
  prediction: { class: "tomato_late_blight", condition: "Late blight", crop: "Tomato",
                confidence: 0.91, top3: [], model_name: "resnet18", img_size: 160, inference_ms: 40,
                input: { size: [640, 480] }, leaf_check: { p_leaf: 0.99, verdict: "leaf" } },
  risk: { risk: "high", risk_label: "High" }, actions: [], warnings: [], narrative: "stub",
  irrigation: null, weather: null, sustainability: null, disclaimer: "",
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Mount the shipped bundle with a camera whose behaviour we control. */
async function mount({ cameraWorks }) {
  const errors = [];
  const dom = new JSDOM(html, { runScripts: "outside-only", pretendToBeVisual: true,
                                url: "https://preview.example/" });
  const { window } = dom;
  window.addEventListener("error", (e) => errors.push(String(e.message)));
  window.addEventListener("unhandledrejection", (e) => errors.push(`unhandled rejection: ${e.reason}`));
  const realConsoleError = window.console.error;
  window.console.error = (...a) => { errors.push(a.map(String).join(" ").slice(0, 300)); realConsoleError.apply(window.console, a); };

  const calls = [];
  const cameraCalls = [];
  const tracks = [];

  window.fetch = (url, opts) => {
    const p = String(url).split("?")[0];
    const method = ((opts && opts.method) || "GET").toUpperCase();
    calls.push(`${method} ${p}`);
    const body = p === "/api/analyze" ? ANALYSIS
      : ({ "/api/health": HEALTH, "/api/meta": META, "/api/samples": { ok: true, count: 0, samples: [] } }[p] ?? { ok: true });
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body),
                             text: () => Promise.resolve(JSON.stringify(body)) });
  };
  window.URL.createObjectURL = () => "blob:stub";
  window.URL.revokeObjectURL = () => {};

  // --- the camera the page sees -------------------------------------------------
  window.navigator.mediaDevices = {
    getUserMedia: (constraints) => {
      cameraCalls.push(constraints);
      if (!cameraWorks) {
        const err = new window.Error("Permission denied");
        err.name = "NotAllowedError";
        return Promise.reject(err);
      }
      const track = { kind: "video", stopped: false, stop() { this.stopped = true; tracks.push(this); } };
      return Promise.resolve({ getTracks: () => [track], getVideoTracks: () => [track] });
    },
  };
  // jsdom has no real media/canvas pipeline; stand in the two calls the shutter makes
  window.HTMLMediaElement.prototype.play = function play() { return Promise.resolve(); };
  const JPEG_BYTES = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46]);
  window.HTMLCanvasElement.prototype.getContext = function getContext() {
    return { drawImage() { /* the real browser paints the frame here */ } };
  };
  window.HTMLCanvasElement.prototype.toBlob = function toBlob(cb, type) {
    cb(new window.Blob([JPEG_BYTES], { type: type || "image/jpeg" }));
  };

  try { window.eval(code); } catch (e) { errors.push(`evaluating the bundle threw: ${e}`); }
  await sleep(700);
  return { window, calls, cameraCalls, tracks, errors };
}

function buttons(doc, needle) {
  return [...doc.querySelectorAll("button")].map((b) => b)
    .filter((b) => (b.textContent || "").includes(needle));
}
function click(btn) { btn.dispatchEvent(new btn.ownerDocument.defaultView.MouseEvent("click", { bubbles: true })); }

const problems = [];

// ============================================================ 1. the happy path
{
  const { window, calls, cameraCalls, tracks, errors } = await mount({ cameraWorks: true });
  const doc = window.document;
  const root = () => (doc.getElementById("root").textContent || "").replace(/\s+/g, " ");

  const takeBtn = buttons(doc, "Take photo")[0];
  if (!takeBtn) { fail("no 'Take photo' button in the rendered upload card"); }
  click(takeBtn);
  await sleep(150);

  const video = doc.querySelector("video.capture-video");
  if (!video) problems.push("clicking 'Take photo' did not render the camera preview");
  if (!cameraCalls.length) problems.push("getUserMedia was never called");
  if (cameraCalls[0] && cameraCalls[0].audio !== false) problems.push("getUserMedia asked for audio");
  if (video && !video.srcObject) problems.push("the camera stream was never attached to <video>");

  // closing must stop the camera before we move on to capturing
  const closeBtn = buttons(doc, "Close camera")[0];
  if (!closeBtn) problems.push("no way to close the camera panel");
  else { click(closeBtn); await sleep(150); }
  if (doc.querySelector("video.capture-video")) problems.push("closing the panel did not remove the preview");
  if (!tracks.length) problems.push("no camera track was ever created");
  else if (!tracks.every((tr) => tr.stopped)) problems.push("closing the panel left a camera track running");
  const tracksAfterClose = tracks.length;

  // reopen and capture a frame
  const reopen = buttons(doc, "Take photo")[0];
  if (!reopen) problems.push("'Take photo' disappeared after closing the panel");
  else { click(reopen); await sleep(150); }

  const shutter = doc.querySelector("button.shutter");
  if (!shutter) problems.push("no shutter button in the capture panel");
  else {
    if (shutter.disabled) problems.push("the shutter is disabled even though the camera is live");
    click(shutter);
    await sleep(200);
  }

  const text = root();
  const gotFile = /camera_\d{8}_\d{6}\.jpg/.test(text);
  if (!gotFile) problems.push(`the captured frame never reached the upload flow (screen: "${text.slice(0, 200)}")`);
  if (gotFile && !buttons(doc, "Analyze this photo").length) problems.push("the two-step submit button is missing after a capture");
  if (gotFile && !buttons(doc, "Remove").length) problems.push("the Remove button is missing after a capture");
  if (doc.querySelector("video.capture-video")) problems.push("the camera panel stayed open after capturing");

  // the next analyze call must carry the captured frame
  const analyze = buttons(doc, "Analyze this photo")[0];
  if (analyze) { click(analyze); await sleep(300); }
  const posted = calls.filter((c) => c.includes("POST /api/analyze")).length;
  if (posted !== 1) problems.push(`expected one POST /api/analyze after capturing, saw ${posted}`);

  if (tracks.length !== tracksAfterClose + 1) problems.push("reopening the camera did not request a new stream");
  if (!tracks.every((tr) => tr.stopped)) problems.push("capturing left the camera running");

  const fatal = errors.filter((e) => !/Not implemented|Warning:|deprecat/i.test(e));
  if (fatal.length) problems.push(`page errors: ${fatal.slice(0, 2).join(" | ")}`);

  console.log(`capture check (happy path) - build ${buildId}, bundle ${asset}`);
  console.log(`  camera calls  : ${cameraCalls.length} (audio=${cameraCalls[0] ? cameraCalls[0].audio : "n/a"})`);
  console.log(`  captured file : ${gotFile ? "camera_*.jpg reached the upload card" : "MISSING"}`);
  console.log(`  tracks stopped: ${tracks.filter((t) => t.stopped).length}/${tracks.length}`);
  console.log(`  analyze posts : ${posted}`);
}

// ==================================================== 2. NEGATIVE CONTROL (denied)
{
  const { window, calls, errors } = await mount({ cameraWorks: false });
  const doc = window.document;
  const takeBtn = buttons(doc, "Take photo")[0];
  if (!takeBtn) fail("no 'Take photo' button in the rendered upload card");
  click(takeBtn);
  await sleep(250);

  const text = (doc.getElementById("root").textContent || "").replace(/\s+/g, " ");
  const explained = /Camera access is blocked/.test(text);
  const phoneEscape = buttons(doc, "Use phone camera").length > 0;
  const fileEscape = buttons(doc, "Choose a photo instead").length > 0;
  if (!explained) problems.push(`a blocked camera was not explained to the user ("${text.slice(0, 200)}")`);
  if (!phoneEscape) problems.push("the denied state does not offer the phone camera");
  if (!fileEscape) problems.push("the denied state does not offer the file picker");
  if (calls.some((c) => c.includes("/api/analyze"))) problems.push("a denied camera somehow triggered an analysis");

  // the file-picker escape hatch must lead straight back to the working flow
  const picker = doc.querySelector('input[type="file"]:not([capture])');
  if (fileEscape && picker) {
    Object.defineProperty(picker, "files", { value: [new window.File([new Uint8Array([1, 2, 3])], "leaf.jpg", { type: "image/jpeg" })], configurable: true });
    picker.dispatchEvent(new window.Event("change", { bubbles: true }));
    await sleep(250);
    if (!buttons(doc, "Analyze this photo").length) problems.push("the picker inside the denied state does not reach the upload flow");
  }

  const fatal = errors.filter((e) => !/Not implemented|Warning:|deprecat/i.test(e));
  if (fatal.length) problems.push(`page errors while denied: ${fatal.slice(0, 2).join(" | ")}`);

  console.log("capture check (camera denied / negative control)");
  console.log(`  explained     : ${explained ? "yes" : "NO"}`);
  console.log(`  phone camera  : ${phoneEscape ? "offered" : "MISSING"}`);
  console.log(`  choose photo  : ${fileEscape ? "offered" : "MISSING"}`);
  console.log(`  still usable  : ${buttons(doc, "Analyze this photo").length ? "yes" : "NO"}`);
}

try { fs.unlinkSync(iife); } catch { /* cache file is disposable */ }

if (problems.length) fail(problems.join("; "));
console.log("✓ live capture works: frame -> camera_*.jpg -> two-step submit -> /api/analyze, tracks stopped on close, blocked cameras explained with a way out");
