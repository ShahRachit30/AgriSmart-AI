#!/usr/bin/env python3
"""Extract the 38-class PlantVillage set (the data behind Kaggle's "New Plant
Diseases Dataset") from the parquet mirror into `data/raw/plantvillage38/<class>/*.jpg`.

Provenance note (be precise in the report):
  * Kaggle `vipoooool/new-plant-diseases-dataset` needs a Kaggle API token. There is
    none on this machine, so we do not download from Kaggle.
  * That dataset describes itself as "recreated using offline augmentation from the
    original dataset", i.e. the 38-class PlantVillage set (spMohanty), split 80/20 into
    train/valid plus 33 test images, with one augmentation per source image.
  * HuggingFace `dpdl-benchmark/plant_village` is a mirror of the same 38-class source
    data with the ORIGINAL filenames - a superset of the Kaggle train/valid splits.
  * `scripts/ingest_kaggle_plantvillage.py` ingests a real Kaggle download instead
    (New Plant Diseases Dataset/{train,valid}/<class>/...), so anyone with a Kaggle
    token can reproduce this exactly from Kaggle; both end in this same folder layout.

Label identity was verified two ways before trusting integers:
  1. per-class counts match the canonical PlantVillage class counts exactly
     (e.g. Apple_scab 630, Tomato_healthy 1591, Orange_Haunglongbing 5507);
  2. a visual contact sheet (`scripts/verify_pv38_labels.py`) for every class whose
     count is ambiguous (the three 1000-image classes, corn healthy/Blight, ...).

Usage:  python scripts/extract_plantvillage38.py            # resume-friendly
        python scripts/extract_plantvillage38.py --report   # just print the manifest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SHARDS = ROOT / "data" / "tmp" / "pv38"
OUT = ROOT / "data" / "raw" / "plantvillage38"

# int label -> class slug (verified; see module docstring)
LABELS = {
    0: "apple_scab", 1: "apple_black_rot", 2: "apple_cedar_apple_rust", 3: "apple_healthy",
    4: "blueberry_healthy", 5: "cherry_healthy", 6: "cherry_powdery_mildew",
    7: "corn_grey_leaf_spot", 8: "corn_common_rust", 9: "corn_healthy",
    10: "corn_northern_leaf_blight", 11: "grape_black_rot", 12: "grape_esca",
    13: "grape_healthy", 14: "grape_leaf_blight", 15: "orange_haunglongbing",
    16: "peach_bacterial_spot", 17: "peach_healthy", 18: "pepper_bacterial_spot",
    19: "pepper_healthy", 20: "potato_early_blight", 21: "potato_healthy",
    22: "potato_late_blight", 23: "raspberry_healthy", 24: "soybean_healthy",
    25: "squash_powdery_mildew", 26: "strawberry_healthy", 27: "strawberry_leaf_scorch",
    28: "tomato_bacterial_spot", 29: "tomato_early_blight", 30: "tomato_healthy",
    31: "tomato_late_blight", 32: "tomato_leaf_mold", 33: "tomato_septoria",
    34: "tomato_spider_mites", 35: "tomato_target_spot",
    36: "tomato_mosaic_virus", 37: "tomato_yellow_leaf_curl_virus",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", action="store_true", help="print counts, write nothing")
    args = ap.parse_args()

    shards = sorted(SHARDS.glob("*.parquet"))
    if not shards:
        print(f"no parquet shards in {SHARDS} - run scripts/download_datasets.py", file=sys.stderr)
        return 2

    counts = {lab: 0 for lab in LABELS}
    written = skipped = 0
    for shard in shards:
        pf = pq.ParquetFile(shard)
        for batch in pf.iter_batches(batch_size=32, columns=["label", "image"]):
            d = batch.to_pydict()
            for lab, img in zip(d["label"], d["image"]):
                raw = (img or {}).get("bytes")
                if raw is None:
                    continue
                slug = LABELS.get(int(lab))
                if slug is None:
                    continue
                counts[int(lab)] += 1
                if args.report:
                    continue
                folder = OUT / slug
                folder.mkdir(parents=True, exist_ok=True)
                dest = folder / f"{slug}_{counts[int(lab)]:05d}.jpg"
                if dest.exists():                       # resume: never rewrite on a restart
                    skipped += 1
                    continue
                dest.write_bytes(raw)
                written += 1
                if written % 2000 == 0:
                    print(f"  {written} written ({written + skipped} scanned)", flush=True)

    if args.report:
        print(f"{len(LABELS)} classes, {sum(counts.values())} images")
        for lab in sorted(counts):
            print(f"  {counts[lab]:>6}  {LABELS[lab]}")
        return 0

    total = sum(counts.values())
    meta = {"n_classes": len(LABELS), "n_images": total,
            "classes": {LABELS[k]: counts[k] for k in sorted(counts)},
            "source": "PlantVillage 38-class set via HuggingFace dpdl-benchmark/plant_village "
                      "(the same source data Kaggle's new-plant-diseases-dataset repackages)",
            "written": written, "already_present": skipped}
    (OUT / "_extract_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"\nwrote {written} new files ({skipped} already there) -> {OUT}")
    print(f"{len(LABELS)} classes, {total} images total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
