#!/usr/bin/env python3
"""Re-score `samples/` with the checkpoint that is actually deployed.

`samples/EXPECTED.md` is a *contract*: the user opens a photo, the app shows a
label, and the table says what should appear. A retrain silently breaks that
contract, so this script re-runs the deployed decoder over every bundled photo
and rewrites

    samples/manifest.json    (machine-readable: what the app will say)
    samples/EXPECTED.md      (human table, grouped by correct / wrong)

It never moves or deletes photos: which files ship is a curation decision
(scripts/curate_samples.py), while this script only refreshes the claim about
what the app does with them. A sample whose true class is no longer predicted
is reported loudly and stays in the table under "the model gets this one wrong"
- that is the honest version of a demo set, not a hidden one.

Usage
-----
    python scripts/verify_samples.py            # re-score + rewrite the table
    python scripts/verify_samples.py --check    # exit 1 if the table is stale
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
if str(ROOT) not in sys.path:          # runnable from anywhere, like the other scripts
    sys.path.insert(0, str(ROOT))


def pretty(slug: str) -> str:
    return slug.replace("_", " ")


# Sample files were named when the app shipped an 18-class model. Two classes were
# renamed for the 38-class vocabulary (the model now says `pepper_healthy` where it
# used to say `bell_pepper_healthy`), so the file name is mapped to the current slug
# before it is compared. Without this the healthy pepper photo would be scored as a
# miss even though the app answers exactly the right class.
LEGACY_LABELS = {
    "bell_pepper_healthy": "pepper_healthy",
    "bell_pepper_bacterial_spot": "pepper_bacterial_spot",
}


def collect() -> list[dict]:
    """Every bundled photo, with its true class taken from the file name."""
    rows = []
    for path in sorted(SAMPLES.rglob("*.jpg")):
        if "non_leaf" in path.parts:      # refusal demos, never in the sample picker
            continue
        name_slug = path.name.split("__", 1)[0]
        true = LEGACY_LABELS.get(name_slug, name_slug)
        rows.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                     "kind": path.parent.name, "true": true, "path": path,
                     "file_label": name_slug if name_slug != true else None})
    return rows


def score(rows: list[dict]) -> list[dict]:
    from model.inference import DiseaseClassifier
    clf = DiseaseClassifier()
    if not clf.available:
        raise SystemExit(f"classifier unavailable: {clf.load_error}")
    for row in rows:
        res = clf.predict(row["path"])
        row["model_says"] = res["class"]
        row["confidence"] = round(float(res["confidence"]), 4)
        row["correct"] = res["class"] == row["true"]
        row["crop"] = res["crop"]
    return rows


def write_expected(rows: list[dict]) -> None:
    right = sorted([r for r in rows if r["correct"]], key=lambda r: -r["confidence"])
    wrong = sorted([r for r in rows if not r["correct"]], key=lambda r: -r["confidence"])
    lines = [
        "# Which sample photo should I test with?",
        "",
        "Every photo below is a **real PlantDoc field photo** (MIT licence, never trained on) "
        "and was scored with **the exact decoding the app runs** (center-crop + leaf-crop "
        "ensemble with mirror TTA) using the deployed checkpoint `model/best_model.pth`. "
        "The *App should say* column is what you will see, so you can check the app against "
        "this table. Regenerate after any retrain with `python scripts/verify_samples.py`.",
        "",
        f"_{len(right)}/{len(rows)} bundled photos are classified correctly; the rest are real "
        "field photos the model still gets wrong and are listed at the bottom on purpose._",
        "",
        "## Recommended first test - classified correctly",
        "",
        "| Sample file | Leaf actually is | App should say | Confidence |",
        "|---|---|---|---|",
    ]
    for r in right:
        lines.append(f"| `{Path(r['file']).name}` | {pretty(r['true'])} | "
                     f"**{pretty(r['model_says'])}** | {r['confidence']:.0%} |")
    lines += [
        "",
        "## Known-hard photos - the app gets these wrong",
        "",
        "Use these to see the honest failure path: the advisory, the low-confidence "
        "handling and the \"verify before spraying\" guidance. They are genuine field "
        "photos, not tricks - PlantDoc simply contains images no lab-trained model can "
        "call from the picture alone.",
        "",
        "| Sample file | Leaf actually is | App says | Confidence |",
        "|---|---|---|---|",
    ]
    for r in wrong:
        lines.append(f"| `{Path(r['file']).name}` | {pretty(r['true'])} | "
                     f"{pretty(r['model_says'])} | {r['confidence']:.0%} |")
    lines += [
        "",
        "## Different crops - do not test these",
        "",
        "`samples/non_leaf/` holds photos that are *not* leaves at all (a chair, a table, "
        "a screenshot). Upload one and the app must **refuse** with \"no leaf detected\" "
        "instead of inventing a disease; the automated tests assert exactly that. They are "
        "deliberately absent from `samples/manifest.json` so they never appear in the "
        "app's sample picker. See `samples/non_leaf/README.md`.",
        "",
    ]
    (SAMPLES / "EXPECTED.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="do not write anything; fail if the checked-in table is stale")
    args = ap.parse_args()

    rows = collect()
    if not rows:
        raise SystemExit("no sample photos found under samples/")
    scored = score(rows)

    if args.check:
        manifest = {m["file"]: m for m in json.loads((SAMPLES / "manifest.json").read_text())}
        stale = [r["file"] for r in scored
                 if manifest.get(r["file"], {}).get("model_says") != r["model_says"]]
        if stale:
            print("stale rows (app says something else now):")
            for s in stale:
                print("  ", s)
            return 1
        print(f"manifest is current for all {len(scored)} samples")
        return 0

    out = [{k: v for k, v in r.items() if k != "path"} for r in scored]
    (SAMPLES / "manifest.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    write_expected(scored)

    n_ok = sum(1 for r in scored if r["correct"])
    print(f"scored {len(scored)} samples: {n_ok} correct, {len(scored) - n_ok} wrong")
    for r in scored:
        mark = "ok  " if r["correct"] else "MISS"
        print(f"  {mark} {Path(r['file']).name[:52]:54s} "
              f"{pretty(r['model_says']):28s} {r['confidence']:.0%}")
    if n_ok < len(scored) - 4:
        print("\nwarning: more than 4 bundled samples are misclassified - consider "
              "re-curating with scripts/curate_samples.py", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
