#!/usr/bin/env python3
"""Build the three splits used by AgriSmart AI.

    data/splits/train       <- PlantVillage (lab, capped per class for CPU training)
    data/splits/val         <- PlantVillage (lab, disjoint from train)
    data/splits/test_field  <- PlantDoc (real field photos, NEVER trained on)

The train/val split uses seed 42 and sharded, per-class caps so the CPU recipe
fits a 2-core sandbox; `--train-per-class 0` reproduces the full-data GPU recipe.

PlantDoc folder names are mapped to our 18 slugs by a normalised lookup table;
folders that do not belong to the 18 shared classes are listed (not silently
dropped) and classes without any field image are reported as ABSENT.

Usage
-----
    python scripts/prepare_data.py
    python scripts/prepare_data.py --train-per-class 0 --val-per-class 0   # full data
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PV_RAW = ROOT / "data" / "raw" / "plantvillage"
PD_RAW = ROOT / "data" / "raw" / "plantdoc"
SPLITS = ROOT / "data" / "splits"

# PlantDoc folder (normalised: lowercase, alphanumerics only) -> our slug
PLANTDOC_MAP: dict[str, str] = {
    "applescableaf": "apple_scab",
    "appleleaf": "apple_healthy",
    "appleblackrotleaf": "apple_black_rot",
    "bellpepperleafspot": "bell_pepper_bacterial_spot",
    "bellpepperleaf": "bell_pepper_healthy",
    "corngrayleafspot": "corn_grey_leaf_spot",
    "cornrustleaf": "corn_common_rust",
    "cornleaf": "corn_healthy",
    "grapeleafblackrot": "grape_black_rot",
    "grapeleaf": "grape_healthy",
    "potatoleafearlyblight": "potato_early_blight",
    "potatoleaflateblight": "potato_late_blight",
    "potatoleaflateblight2": "potato_late_blight",
    "potatoleaf": "potato_healthy",
    "tomatoleafbacterialspot": "tomato_bacterial_spot",
    "tomatoearlyblightleaf": "tomato_early_blight",
    "tomatoleaflateblight": "tomato_late_blight",
    "tomatomoldleaf": "tomato_leaf_mold",
    "tomatoleaf": "tomato_healthy",
}
SUPPORTED = frozenset(
    """apple_scab apple_black_rot apple_healthy bell_pepper_bacterial_spot bell_pepper_healthy
       corn_grey_leaf_spot corn_common_rust corn_healthy grape_black_rot grape_healthy
       potato_early_blight potato_late_blight potato_healthy tomato_bacterial_spot
       tomato_early_blight tomato_late_blight tomato_leaf_mold tomato_healthy""".split()
)


def norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def link_or_copy(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    if mode == "copy":
        shutil.copy2(src, dst)
        return
    try:
        dst.hardlink_to(src)
    except Exception:
        shutil.copy2(src, dst)


def build_imagefolder_split(pairs: list[tuple[Path, str]], split: str, mode: str) -> dict[str, int]:
    out = SPLITS / split
    if out.exists():
        shutil.rmtree(out)
    counts: dict[str, int] = {}
    for src, slug in pairs:
        n = counts.get(slug, 0)
        link_or_copy(src, out / slug / f"{slug}_{n:05d}{src.suffix.lower()}", mode)
        counts[slug] = n + 1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-per-class", type=int, default=400, help="0 = all")
    ap.add_argument("--val-per-class", type=int, default=60, help="0 = all")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--mode", choices=["hardlink", "copy"], default="copy")
    a = ap.parse_args()
    rng = random.Random(a.seed)

    # ---------------- lab splits (PlantVillage) ---------------- #
    if not PV_RAW.exists():
        raise SystemExit(f"missing {PV_RAW} - run download + extract first")
    classes = sorted(d for d in PV_RAW.iterdir() if d.is_dir() and d.name in SUPPORTED)
    if not classes:
        raise SystemExit("no PlantVillage class folders found")
    train_pairs: list[tuple[Path, str]] = []
    val_pairs: list[tuple[Path, str]] = []
    per_class_report: dict[str, dict[str, int]] = {}
    for cdir in classes:
        imgs = sorted(p for p in cdir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        rng.shuffle(imgs)
        n_tr = len(imgs) if a.train_per_class == 0 else min(a.train_per_class, max(0, len(imgs) - 1))
        n_va = a.val_per_class if a.val_per_class == 0 else min(a.val_per_class, max(0, len(imgs) - n_tr))
        tr, va = imgs[:n_tr], imgs[n_tr:n_tr + n_va]
        train_pairs += [(p, cdir.name) for p in tr]
        val_pairs += [(p, cdir.name) for p in va]
        per_class_report[cdir.name] = {"available": len(imgs), "train": len(tr), "val": len(va)}
    tr_counts = build_imagefolder_split(train_pairs, "train", a.mode)
    va_counts = build_imagefolder_split(val_pairs, "val", a.mode)
    print(f"[train] {sum(tr_counts.values())} images / {len(tr_counts)} classes -> {SPLITS / 'train'}")
    print(f"[val]   {sum(va_counts.values())} images / {len(va_counts)} classes -> {SPLITS / 'val'}")

    # ---------------- field split (PlantDoc) ---------------- #
    field_counts: dict[str, int] = {}
    unmapped: dict[str, int] = {}
    field_pairs: list[tuple[Path, str]] = []
    if PD_RAW.exists():
        for d in sorted(p for p in PD_RAW.rglob("*") if p.is_dir()):
            slug = PLANTDOC_MAP.get(norm(d.name))
            imgs = sorted(p for p in d.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
            if not imgs:
                continue
            if slug is None:
                unmapped[d.name] = unmapped.get(d.name, 0) + len(imgs)
                continue
            field_pairs += [(p, slug) for p in imgs]
        field_counts = build_imagefolder_split(field_pairs, "test_field", a.mode)
        print(f"[field] {sum(field_counts.values())} images / {len(field_counts)} classes -> {SPLITS / 'test_field'}")
        if unmapped:
            print("  PlantDoc folders outside our 18 classes (ignored on purpose):")
            for k, v in sorted(unmapped.items(), key=lambda kv: -kv[1]):
                print(f"    - {k} ({v})")
    else:
        print("[field] WARNING PlantDoc not downloaded - skipping field split")

    absent = sorted(SUPPORTED - set(field_counts)) if field_counts else []
    if absent:
        print(f"  field-absent classes (excluded from field macro-F1): {absent}")

    meta = {
        "seed": a.seed,
        "train": tr_counts,
        "val": va_counts,
        "test_field": field_counts,
        "per_class_available": per_class_report,
        "field_absent_classes": absent,
        "plantdoc_map": PLANTDOC_MAP,
    }
    SPLITS.mkdir(parents=True, exist_ok=True)
    (SPLITS / "split_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"\nwrote {SPLITS / 'split_meta.json'}")
    print("Next: python model/train.py --data data/splits --model resnet18 --img-size 192 "
          "--epochs 8 --batch-size 64 --workers 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
