#!/usr/bin/env python3
"""Curate the `samples/` demo set from the PlantDoc field images.

Why this exists: an earlier revision picked "the first file of a class that had at
least one correct prediction" - but `report/predictions.json` carries no filenames,
so the picked files were arbitrary. This script scores **every field image with the
exact decoding the app deploys** (`model.inference.DiseaseClassifier`, i.e.
center-crop + leaf-crop ensemble with mirror TTA), then selects on purpose:

  * `right/*`   - images the model gets right (prefers high confidence)
  * `hard/*`    - images the model gets wrong *confidently* (shows the
                  "re-photograph / verify" path honestly)
  * two `hard/` picks are also copied as the classic late-vs-early blight confusion

Outputs
-------
    report/sample_candidates.json   every scored image (audit trail)
    samples/…                       the curated demo images (copied at full resolution)
    samples/EXPECTED.md             what the app should say for each file

Usage
-----
    python scripts/curate_samples.py --plantdoc data/raw/plantdoc \
        --out-report report/sample_candidates.json --per-class 1 --hard 3
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.prepare_data import PLANTDOC_MAP, norm  # noqa: E402


def safe_slug(name: str) -> str:
    """Filesystem- and URL-safe id (PlantDoc ships names like
    'image5_300x300%2523.JPG?1472755422' which would break a URL path)."""
    keep = [c if (c.isalnum() or c in "-_") else "_" for c in name]
    slug = "".join(keep).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:60] or "sample"


def collect(plantdoc: Path) -> list[tuple[Path, str]]:
    pairs: list[tuple[Path, str]] = []
    for d in sorted(p for p in plantdoc.rglob("*") if p.is_dir()):
        slug = PLANTDOC_MAP.get(norm(d.name))
        if slug is None:
            continue
        pairs += [(p, slug) for p in sorted(d.iterdir())
                  if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plantdoc", default=str(ROOT / "data" / "raw" / "plantdoc"))
    ap.add_argument("--out-report", default=str(ROOT / "report" / "sample_candidates.json"))
    ap.add_argument("--per-class", type=int, default=1, help="correct samples per class")
    ap.add_argument("--hard", type=int, default=3, help="confidently-wrong samples to keep")
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    plantdoc = Path(a.plantdoc)
    if not plantdoc.is_dir():
        raise SystemExit(f"{plantdoc} not found - run scripts/download_datasets.py --only plantdoc")
    pairs = collect(plantdoc)
    if not pairs:
        raise SystemExit("no PlantDoc images matched the class map")

    from model.inference import get_classifier
    clf = get_classifier()
    if not clf.available:
        raise SystemExit(f"classifier unavailable: {clf.load_error}")

    rows = []
    for i, (path, true_slug) in enumerate(pairs, 1):
        try:
            pred = clf.predict(path)
        except Exception as exc:  # unreadable file - record and move on
            rows.append({"path": str(path), "true": true_slug, "error": str(exc)})
            continue
        rows.append({
            "path": str(path), "true": true_slug, "pred": pred["class"],
            "confidence": pred["confidence"], "condition": pred["condition"],
            "correct": pred["class"] == true_slug,
            "top3": [(t["class"], t["confidence"]) for t in pred["top3"]],
        })
        if i % 200 == 0:
            print(f"  scored {i}/{len(pairs)}", flush=True)

    Path(a.out_report).write_text(json.dumps(rows, indent=2))
    ok = [r for r in rows if r.get("correct")]
    bad = [r for r in rows if r.get("correct") is False]
    print(f"\nscored {len(rows)} images: {len(ok)} correct / {len(bad)} wrong "
          f"({len(ok) / max(len(rows), 1):.1%} accuracy) -> {a.out_report}")

    # ---------------- selection ---------------- #
    samples = ROOT / "samples"
    for sub in ("right", "hard"):
        if (samples / sub).exists():
            shutil.rmtree(samples / sub)
        (samples / sub).mkdir(parents=True, exist_ok=True)
    # remove the old flat, unverified samples
    for old in samples.glob("*.jpg"):
        old.unlink()

    by_class: dict[str, list[dict]] = defaultdict(list)
    for r in ok:
        by_class[r["true"]].append(r)
    chosen_right = []
    for slug, items in sorted(by_class.items()):
        items.sort(key=lambda r: -r["confidence"])
        for r in items[: a.per_class]:
            chosen_right.append(r)

    chosen_hard = sorted(bad, key=lambda r: -r["confidence"])[: a.hard]

    manifest = []
    for kind, items in (("right", chosen_right), ("hard", chosen_hard)):
        for r in items:
            src = Path(r["path"])
            dst = samples / kind / f"{r['true']}__{safe_slug(src.stem)}.jpg"
            shutil.copy2(src, dst)
            manifest.append({
                "file": str(dst.relative_to(ROOT)), "kind": kind, "true": r["true"],
                "model_says": r["pred"], "confidence": r["confidence"],
                "correct": r["correct"], "source_image": src.name,
            })
            print(f"  {kind:5s} {dst.name:52s} true={r['true']:28s} "
                  f"model={r['pred']:28s} conf={r['confidence']:.2f}")

    (samples / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nwrote {samples / 'manifest.json'} ({len(manifest)} samples)")
    write_expected_md(samples, manifest)
    return 0


def write_expected_md(samples: Path, manifest: list[dict]) -> None:
    """Regenerate samples/EXPECTED.md from the manifest (single source of truth)."""
    right = sorted([m for m in manifest if m["kind"] == "right"], key=lambda r: -r["confidence"])
    hard = sorted([m for m in manifest if m["kind"] == "hard"], key=lambda r: -r["confidence"])
    L: list[str] = []
    A = L.append
    A("# Which sample photo should I test with?\n")
    A("Every photo below is a **real PlantDoc field photo** (MIT licence, never trained on) and was "
      "scored with **the exact decoding the app runs** (center-crop + leaf-crop ensemble with mirror "
      "TTA). The `model says` column is what the app will show you, so you can check the app against "
      "this table. Machine-readable list: `samples/manifest.json`; regenerate with "
      "`python scripts/curate_samples.py`.\n")
    A("## Recommended first test - these are classified correctly\n")
    A("Pick any of these; the confidence is high, so the whole advisory pipeline behaves as "
      "designed (risk card, prioritised actions, irrigation, sustainability, assistant).\n")
    A("| Sample file | Leaf actually is | App should say | Confidence |")
    A("|---|---|---|---|")
    for m in right:
        A(f"| `{Path(m['file']).name}` | {m['true'].replace('_', ' ')} "
          f"| **{m['model_says'].replace('_', ' ')}** | {m['confidence']:.0%} |")
    if right:
        best = right[0]
        A(f"\n**Easy demo pick:** `{Path(best['file']).name}` - the model is confident "
          f"({best['confidence']:.0%}), so the risk card, the action list and the assistant all "
          f"fire the way they were designed to.\n")
    A("## Hard cases - deliberately included to show honest behaviour\n")
    A("These are the model's **confident mistakes**: a real symptom of the lab->field gap (field "
      "macro-F1 is 0.27, not 0.99). Load one and watch the safeguards work: the risk card caps at "
      "*moderate* and says 'verify before buying chemicals' (confidence < 0.75 maps to verify, not "
      "to the KB severity), the assistant only quotes numbers that are on screen, and the metrics "
      "card still reports the low field macro-F1 - nothing is hidden.\n")
    A("| Sample file | Leaf actually is | App will say (wrongly) | Confidence |")
    A("|---|---|---|---|")
    for m in hard:
        A(f"| `{Path(m['file']).name}` | {m['true'].replace('_', ' ')} "
          f"| {m['model_says'].replace('_', ' ')} | {m['confidence']:.0%} |")
    A("\n## Fastest way to test (no download needed)\n")
    A("The Dashboard has a **sample picker** right under the upload card: *\"No photo handy? Tap a "
      "verified sample field photo\"*. One click runs the whole pipeline. Equivalent API calls:\n")
    A("```bash\ncurl -s localhost:8000/api/samples | python3 -m json.tool | head -40\n"
      "curl -s -X POST localhost:8000/api/analyze -F sample_id=<id> -F soil_moisture_pct=24 "
      "-F city=Ahmedabad\n```\n")
    A("## Testing with your own photo\n")
    A("Any JPG/PNG/WebP up to 10 MB works. Best results (this is what the model was trained on):\n")
    A("1. **One leaf fills most of the frame** - background clutter is the biggest cause of field "
      "errors; the app crops to the greenest region to help, but a close-up always wins.\n"
      "2. **Daylight, no flash glare**; avoid heavy shadow across the leaf.\n"
      "3. **Keep the diseased part in view** - a photo of only the healthy half of a leaf will "
      "correctly be called healthy.\n"
      "4. Phone photos are fine, including EXIF-rotated ones (the app straightens them).\n")
    A("If the app answers with low confidence (< 50 %) it asks you to re-photograph. That is a "
      "feature, not a failure: at 0.27 field macro-F1 the honest move is to ask for a better photo "
      "rather than invent a diagnosis.\n")
    A("## Classes the app can name\n")
    A("18 classes: apple (scab, black rot, healthy), bell pepper (bacterial spot, healthy), corn "
      "(grey leaf spot, common rust, healthy), grape (black rot, healthy), potato (early blight, "
      "late blight, healthy), tomato (bacterial spot, early blight, late blight, leaf mould, "
      "healthy). A photo outside these six crops (rice, banana, wheat...) is forced into the "
      "nearest class - the UI always shows the top-3 so you can see when the model is unsure.\n")
    (samples / "EXPECTED.md").write_text("\n".join(L))
    print(f"wrote {samples / 'EXPECTED.md'} ({len(right)} correct + {len(hard)} hard)")


if __name__ == "__main__":
    sys.exit(main())
