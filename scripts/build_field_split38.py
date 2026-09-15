#!/usr/bin/env python3
"""Build the honest FIELD splits for the 38-class model from PlantDoc.

PlantDoc has 27 folders; with the 38-class vocabulary **25 of them** map onto a class we
now predict (the 18-class model could only use 19 of them and had to drop
corn leaf blight, tomato septoria, squash powdery mildew, raspberry, blueberry, peach,
cherry, strawberry, soybean and the spider-mite folder entirely). Everything grows:
more classes scored, and a fair test that includes the crops the new model covers.

Splits (seed 42), all written as symlinks:
  train_field   80 % of PlantDoc `train`
  val_field     20 % of PlantDoc `train` (model selection during stage-2 adaptation)
  test_field    PlantDoc `test` - the official, never-trained split
  holdout_field PlantDoc `test` + the 20 % held out of `train` (larger secondary evidence)

Usage:  python scripts/build_field_split38.py [--report]
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# PlantDoc is fetched by scripts/download_datasets.py into data/raw/plantdoc; older
# checkouts extracted the GitHub tarball under data/tmp/pd/. Accept both, and an
# explicit --plantdoc, so the field split can always be rebuilt.
PD_CANDIDATES = [ROOT / "data" / "raw" / "plantdoc",
                 ROOT / "data" / "tmp" / "pd" / "PlantDoc-Dataset-master"]
PD = next((p for p in PD_CANDIDATES if (p / "train").is_dir()), PD_CANDIDATES[0])
OUT = ROOT / "data" / "splits_field38"
CLASS_JSON = ROOT / "model" / "class_names38.json"
SEED = 42

# PlantDoc folder -> our class slug (every folder that has a class in the 38-set)
PLANTDOC_MAP = {
    "Apple Scab Leaf": "apple_scab",
    "Apple leaf": "apple_healthy",
    "Apple rust leaf": "apple_cedar_apple_rust",
    "Bell_pepper leaf": "bell_pepper_healthy",
    "Bell_pepper leaf spot": "bell_pepper_bacterial_spot",
    "Blueberry leaf": "blueberry_healthy",
    "Cherry leaf": "cherry_healthy",
    "Corn Gray leaf spot": "corn_grey_leaf_spot",
    "Corn leaf blight": "corn_northern_leaf_blight",
    "Corn rust leaf": "corn_common_rust",
    "Peach leaf": "peach_healthy",
    "Potato leaf early blight": "potato_early_blight",
    "Potato leaf late blight": "potato_late_blight",
    "Raspberry leaf": "raspberry_healthy",
    "Soyabean leaf": "soybean_healthy",
    "Squash Powdery mildew leaf": "squash_powdery_mildew",
    "Strawberry leaf": "strawberry_healthy",
    "Tomato Early blight leaf": "tomato_early_blight",
    "Tomato Septoria leaf spot": "tomato_septoria",
    "Tomato leaf": "tomato_healthy",
    "Tomato leaf bacterial spot": "tomato_bacterial_spot",
    "Tomato leaf late blight": "tomato_late_blight",
    "Tomato leaf mosaic virus": "tomato_mosaic_virus",
    "Tomato leaf yellow virus": "tomato_yellow_leaf_curl_virus",
    "Tomato mold leaf": "tomato_leaf_mold",
    "Tomato two spotted spider mites leaf": "tomato_spider_mites",
    "grape leaf": "grape_healthy",
    "grape leaf black rot": "grape_black_rot",
}
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def class_order() -> list[str]:
    return list(json.loads(CLASS_JSON.read_text())["order"])


def collect(root: Path, order: list[str]) -> dict[str, list[Path]]:
    """{slug: [paths]} for every mapped PlantDoc folder under `root`."""
    out: dict[str, list[Path]] = defaultdict(list)
    if not root.is_dir():
        return out
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        slug = PLANTDOC_MAP.get(folder.name)
        if slug not in order:
            continue
        for f in sorted(folder.iterdir()):
            if f.suffix.lower() in IMG_EXT:
                out[slug].append(f)
    return dict(out)


def link(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        try:
            dest.symlink_to(src)
        except OSError:
            import shutil
            shutil.copy2(src, dest)


def write_split(name: str, by_class: dict[str, list[Path]]) -> int:
    total = 0
    for slug, files in by_class.items():
        for f in files:
            link(f, OUT / name / slug / f.name)
            total += 1
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--plantdoc", default=None, help="PlantDoc root (train/ + test/)")
    args = ap.parse_args()

    global PD
    from pathlib import Path as _P
    PD = _P(args.plantdoc) if args.plantdoc else PD

    order = class_order()
    train_all = collect(PD / "train", order)
    test_all = collect(PD / "test", order)
    if not train_all:
        raise SystemExit(f"no PlantDoc images under {PD} - run scripts/download_datasets.py")

    rng = random.Random(SEED)
    train, holdout = {}, {}
    for slug, files in train_all.items():
        files = sorted(files)
        rng.shuffle(files)
        cut = max(1, int(round(len(files) * 0.2)))
        holdout[slug] = sorted(files[:cut])
        train[slug] = sorted(files[cut:])

    merged_holdout = {s: sorted(set(holdout.get(s, [])) | set(test_all.get(s, [])))
                      for s in set(holdout) | set(test_all)}

    plan = {
        "train_field": {s: len(v) for s, v in sorted(train.items())},
        "val_field": {s: len(v) for s, v in sorted(holdout.items())},
        "test_field": {s: len(v) for s, v in sorted(test_all.items())},
        "holdout_field": {s: len(v) for s, v in sorted(merged_holdout.items())},
    }
    if args.report:
        for name, counts in plan.items():
            print(f"{name}: {sum(counts.values())} images, {len(counts)} classes")
            for s, n in counts.items():
                print(f"   {s:34s} {n}")
        return 0

    sizes = {name: write_split(name, data) for name, data in (
        ("train_field", train), ("val_field", holdout),
        ("test_field", test_all), ("holdout_field", merged_holdout))}

    all_slugs = sorted(set().union(*[set(c) for c in plan.values()]))
    meta = {
        "n_classes_total": len(order), "n_classes_scored": len(all_slugs),
        "classes_scored": all_slugs,
        "classes_absent_from_plantdoc": [c for c in order if c not in all_slugs],
        "sizes": sizes, "per_class": plan, "seed": SEED,
        "source": "PlantDoc-Dataset (MIT, pratikkayal) - official test split + 80/20 of train",
        "note": "every reported field number is on images the model never trained on",
    }
    (OUT / "split_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {OUT}")
    for name, n in sizes.items():
        print(f"  {name:15s} {n:5d} images")
    print(f"  scored classes: {len(all_slugs)} of {len(order)} "
          f"(absent: {', '.join(meta['classes_absent_from_plantdoc'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
