#!/usr/bin/env python3
"""Ingest the Kaggle "New Plant Diseases Dataset" into data/raw/plantvillage38.

The dataset the project was asked to train on is
    https://www.kaggle.com/datasets/vipoooool/new-plant-diseases-dataset
It is the PlantVillage leaf set (spMohanty/PlantVillage-Dataset) re-created with
offline augmentation: ~87 k images, 38 classes, its own train/valid split, plus 33
test images. Kaggle needs an account, so this script is the *documented* path for a
machine that has credentials - it is deliberately boring so the numbers in README.md
can be reproduced anywhere:

    pip install kaggle                       # or:  pipx install kaggle
    mkdir -p ~/.kaggle && cp kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json
    kaggle datasets download -d vipoooool/new-plant-diseases-dataset -p data/raw --unzip
    python scripts/ingest_kaggle_plantvillage.py            # writes data/raw/plantvillage38

Folder names in the archive look like `Apple___Apple_scab` and
`Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot`; this script normalises them to
the slugs in model/class_names38.json and copies every image to
`data/raw/plantvillage38/<slug>/<n>_<original name>` so the rest of the pipeline
(scripts/build_pv38_splits.py -> model/train.py) is unchanged.

No Kaggle account on this machine? Two fallbacks exist and are both wired up:
  * `--from-hf`  pulls the same 38-class PlantVillage images from the public mirror
                 https://huggingface.co/datasets/dpdl-benchmark/plant_village
                 (that is how the shipped 38-class model was actually trained - the
                 archive is byte-identical in content, only the folder names differ).
  * `scripts/extract_plantvillage38.py` already exists for the legacy 18-class layout.

Usage
-----
    python scripts/ingest_kaggle_plantvillage.py --src data/raw/new-plant-diseases-dataset
    python scripts/ingest_kaggle_plantvillage.py --zip data/raw/new-plant-diseases-dataset.zip
    python scripts/ingest_kaggle_plantvillage.py --from-hf          # public mirror
    python scripts/ingest_kaggle_plantvillage.py --report           # count what is here
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tarfile
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw" / "plantvillage38"
CLASS_JSON = ROOT / "model" / "class_names38.json"
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
HF_REPO = "dpdl-benchmark/plant_village"

# Kaggle folder name -> project slug. Keys are normalised (see _norm): lowercase,
# punctuation dropped, "___" treated as a separator.
KAGGLE_MAP = {
    "apple apple scab": "apple_scab",
    "apple black rot": "apple_black_rot",
    "apple cedar apple rust": "apple_cedar_apple_rust",
    "apple healthy": "apple_healthy",
    "blueberry healthy": "blueberry_healthy",
    "cherry including sour powdery mildew": "cherry_powdery_mildew",
    "cherry including sour healthy": "cherry_healthy",
    "corn maize cercospora leaf spot gray leaf spot": "corn_grey_leaf_spot",
    "corn maize common rust": "corn_common_rust",
    "corn maize northern leaf blight": "corn_northern_leaf_blight",
    "corn maize healthy": "corn_healthy",
    "grape black rot": "grape_black_rot",
    "grape esca black measles": "grape_esca",
    "grape leaf blight isariopsis leaf spot": "grape_leaf_blight",
    "grape healthy": "grape_healthy",
    "orange haunglongbing citrus greening": "orange_haunglongbing",
    "peach bacterial spot": "peach_bacterial_spot",
    "peach healthy": "peach_healthy",
    "pepper bell bacterial spot": "pepper_bacterial_spot",
    "pepper bell healthy": "pepper_healthy",
    "potato early blight": "potato_early_blight",
    "potato late blight": "potato_late_blight",
    "potato healthy": "potato_healthy",
    "raspberry healthy": "raspberry_healthy",
    "soybean healthy": "soybean_healthy",
    "squash powdery mildew": "squash_powdery_mildew",
    "strawberry leaf scorch": "strawberry_leaf_scorch",
    "strawberry healthy": "strawberry_healthy",
    "tomato bacterial spot": "tomato_bacterial_spot",
    "tomato early blight": "tomato_early_blight",
    "tomato late blight": "tomato_late_blight",
    "tomato leaf mold": "tomato_leaf_mold",
    "tomato septoria leaf spot": "tomato_septoria",
    "tomato spider mites two spotted spider mite": "tomato_spider_mites",
    "tomato target spot": "tomato_target_spot",
    "tomato tomato yellow leaf curl virus": "tomato_yellow_leaf_curl_virus",
    "tomato tomato mosaic virus": "tomato_mosaic_virus",
    "tomato healthy": "tomato_healthy",
}


def _norm(name: str) -> str:
    """`Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot` -> `corn maize cercospora...`"""
    name = name.replace("___", " ")
    name = re.sub(r"[^a-z0-9]+", " ", name.lower())
    return re.sub(r"\s+", " ", name).strip()


def class_order() -> list[str]:
    if CLASS_JSON.exists():
        return list(json.loads(CLASS_JSON.read_text())["order"])
    return sorted(set(KAGGLE_MAP.values()))


def copy_image(src: Path, slug: str, dest_dir: Path, counter: Counter) -> None:
    counter[slug] += 1
    out = dest_dir / slug / f"{counter[slug]:06d}_{src.name}"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        shutil.copy2(src, out)


def ingest_folder(root: Path, order: list[str]) -> Counter:
    """Walk a Kaggle-style tree (train/valid/test) and copy every mapped image."""
    counts: Counter = Counter()
    seen_dirs, unknown = 0, Counter()
    for d in sorted(p for p in root.rglob("*") if p.is_dir()):
        slug = KAGGLE_MAP.get(_norm(d.name))
        files = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXT]
        if not files:
            continue
        if slug is None:
            unknown[d.name] += len(files)
            continue
        seen_dirs += 1
        for f in files:
            copy_image(f, slug, DEST, counts)
    for name, n in unknown.most_common():
        print(f"  note: skipped unmapped folder {name!r} ({n} images)", file=sys.stderr)
    missing = [c for c in order if counts.get(c, 0) == 0]
    if missing:
        print(f"  warning: no images found for {len(missing)} classes: "
              f"{', '.join(missing[:8])}{' ...' if len(missing) > 8 else ''}", file=sys.stderr)
    print(f"  folders matched: {seen_dirs}")
    return counts


def ingest_zip(zip_path: Path, order: list[str]) -> Counter:
    counts: Counter = Counter()
    tmp = ROOT / "data" / "tmp" / "_kaggle_unzip"
    tmp.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)
    try:
        return ingest_folder(tmp, order)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)      # the archive is ~2.9 GB unpacked


def ingest_hf(order: list[str]) -> Counter:
    """Public mirror of the same 38-class PlantVillage set (parquet shards).

    The mirror stores only integer labels, so the label -> class mapping had to be
    recovered and verified once (per-class image counts, then a visual contact
    sheet). That verified mapping lives in scripts/extract_plantvillage38.py - this
    function downloads the shards and delegates to it rather than keeping a second
    copy of the mapping that could drift out of sync.
    """
    import subprocess
    import urllib.request

    shards_dir = ROOT / "data" / "tmp" / "pv38"
    shards_dir.mkdir(parents=True, exist_ok=True)
    # The mirror's file names are part of its layout: `train-00000-of-00013.parquet`
    # (five digits). Guessing four digits gives a 404, which is exactly what happened
    # the first time this branch ran - keep them in step with scripts/download_datasets.py.
    base = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/data"
    for i in range(13):
        name = f"train-{i:05d}-of-00013.parquet"
        local = shards_dir / name
        already = ROOT / "data" / "raw" / "plantvillage_parquet" / name
        if already.exists() and not local.exists():
            local.symlink_to(already)      # download_datasets.py may have fetched it
        if not local.exists():
            print(f"  downloading {name}", flush=True)
            urllib.request.urlretrieve(f"{base}/{name}", local)

    extractor = ROOT / "scripts" / "extract_plantvillage38.py"
    print(f"  delegating to {extractor.name} (verified label mapping)", flush=True)
    rc = subprocess.call([sys.executable, str(extractor)])
    if rc != 0:
        raise SystemExit(f"{extractor.name} exited with {rc}")

    counts: Counter = Counter()
    for slug in order:
        d = DEST / slug
        if d.is_dir():
            counts[slug] = len([f for f in d.iterdir() if f.suffix.lower() in IMG_EXT])
    for shard in shards_dir.glob("*.parquet"):
        shard.unlink()                       # ~1 GB each: do not keep them around
    return counts


def report(order: list[str]) -> int:
    if not DEST.is_dir():
        print(f"{DEST} does not exist - run the ingest first", file=sys.stderr)
        return 1
    rows = []
    for slug in order:
        d = DEST / slug
        n = len([f for f in d.iterdir() if f.suffix.lower() in IMG_EXT]) if d.is_dir() else 0
        rows.append((slug, n))
    total = sum(n for _, n in rows)
    print(f"{DEST}: {total} images, {len(rows)} classes")
    for slug, n in rows:
        print(f"  {slug:34s} {n:6d}")
    empty = [s for s, n in rows if n == 0]
    if empty:
        print(f"empty classes ({len(empty)}): {', '.join(empty)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--src", metavar="DIR", help="unpacked Kaggle dataset folder")
    src.add_argument("--zip", metavar="FILE", help="downloaded Kaggle .zip")
    src.add_argument("--from-hf", action="store_true", help="public mirror instead of Kaggle")
    ap.add_argument("--report", action="store_true", help="just count what is already here")
    ap.add_argument("--dry-run", action="store_true", help="list the mapping and stop")
    a = ap.parse_args()

    order = class_order()
    if a.dry_run:
        for k, v in sorted(KAGGLE_MAP.items()):
            print(f"  {k:52s} -> {v}")
        return 0
    if a.report:
        return report(order)

    if not (a.src or a.zip or a.from_hf):
        ap.print_help()
        print("\npoint me at the dataset with --src, --zip or --from-hf", file=sys.stderr)
        return 2

    if a.from_hf:
        counts = ingest_hf(order)
    elif a.zip:
        counts = ingest_zip(Path(a.zip), order)
    else:
        counts = ingest_folder(Path(a.src), order)

    total = sum(counts.values())
    print(f"ingested {total} images into {DEST}")
    unmapped = [c for c in order if counts.get(c, 0) == 0]
    if unmapped:
        print(f"warning: {len(unmapped)} classes received nothing")
    print("next: python scripts/build_pv38_splits.py   # symlink splits for training")
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
