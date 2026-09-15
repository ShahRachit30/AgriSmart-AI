#!/usr/bin/env python3
"""Build the **field** splits used by the v2 domain-adaptation round.

Why this file exists
--------------------
The v1 model was trained on PlantVillage only. Its "field test" was every
PlantDoc image in our 18 classes (train **and** test folders, 1,318 images) -
legitimate for v1, because those images were never trained on.

For v2 we *do* want to train on field photos (that is the whole point of domain
adaptation), so the evaluation protocol has to be rebuilt honestly:

    data/splits_field/train_field   PlantDoc train folder, 80 % (stratified)  -> trained on
    data/splits_field/val_field     PlantDoc train folder, 20 % (stratified)  -> epoch selection only
    data/splits_field/test_field    PlantDoc test folder, 100 %               -> touched once, at the end

The official PlantDoc test folder holds only 128 of our 18 classes, which is a
noisy basis for a macro-F1, so we report **two** numbers and label them
explicitly:

    field/test          n=128   official split, never seen in any form
    field/holdout       n=366   test + the 20 % train holdout (never trained on)

Classes absent from PlantDoc (corn_healthy, potato_healthy, ...) stay in the
class list - they are simply not scored on field data, exactly as in v1.

Usage
-----
    python scripts/build_field_split.py                 # -> data/splits_field
    python scripts/build_field_split.py --holdout 0.2
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prepare_data import PLANTDOC_MAP, norm  # noqa: E402  (shared, verified table)

PD_RAW = ROOT / "data" / "raw" / "plantdoc"
OUT = ROOT / "data" / "splits_field"
CLASS_JSON = ROOT / "model" / "class_names.json"
IMG_EXTS = {".jpg", ".jpeg", ".png"}


def class_order() -> list[str]:
    """Our 18 slugs, in the order the checkpoint uses (index = label)."""
    return list(json.loads(CLASS_JSON.read_text())["order"])


def _plantdoc_root() -> Path:
    """Accept either data/raw/plantdoc/<train|test>/ or a freshly extracted tarball."""
    if (PD_RAW / "train").is_dir():
        return PD_RAW
    hits = sorted(p for p in PD_RAW.rglob("train") if p.is_dir())
    if not hits:
        raise SystemExit(f"PlantDoc train/test folders not found under {PD_RAW}")
    return hits[0].parent


def collect(split_dir: Path, order: list[str]) -> dict[str, list[Path]]:
    """{slug: [image paths]} for one PlantDoc split folder, mapped to our slugs."""
    idx = {c: i for i, c in enumerate(order)}
    out: dict[str, list[Path]] = {}
    for d in sorted(p for p in split_dir.rglob("*") if p.is_dir()):
        slug = PLANTDOC_MAP.get(norm(d.name))
        if slug not in idx:            # not one of our 18 classes - deliberately skipped
            continue
        imgs = sorted(p for p in d.iterdir() if p.suffix.lower() in IMG_EXTS)
        if imgs:
            out.setdefault(slug, []).extend(imgs)
    return out


def write_split(name: str, per_class: dict[str, list[Path]]) -> dict[str, int]:
    dest = OUT / name
    if dest.exists():
        shutil.rmtree(dest)
    counts: dict[str, int] = {}
    for slug, paths in sorted(per_class.items()):
        for i, src in enumerate(sorted(paths)):
            dst = dest / slug / f"{slug}_{i:05d}{src.suffix.lower()}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                dst.hardlink_to(src)
            except Exception:
                shutil.copy2(src, dst)
        counts[slug] = len(paths)
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--holdout", type=float, default=0.20,
                    help="fraction of PlantDoc train kept for epoch selection")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    order = class_order()
    pd_root = _plantdoc_root()
    rng = random.Random(a.seed)

    train_all = collect(pd_root / "train", order)
    test_all = collect(pd_root / "test", order)

    train_keep: dict[str, list[Path]] = {}
    holdout: dict[str, list[Path]] = {}
    for slug, paths in train_all.items():
        paths = list(paths)
        rng.shuffle(paths)
        n_hold = max(1, int(round(len(paths) * a.holdout)))
        holdout[slug] = paths[:n_hold]
        train_keep[slug] = paths[n_hold:]

    tr = write_split("train_field", train_keep)
    va = write_split("val_field", holdout)
    te = write_split("test_field", test_all)
    # "holdout_field" = everything the model never trains on: the official test folder
    # plus the 20 % of the train folder we kept back for epoch selection.
    hold = {slug: (list(test_all.get(slug, [])) + list(holdout.get(slug, [])))
            for slug in set(test_all) | set(holdout)}
    ho = write_split("holdout_field", hold)

    meta = {
        "protocol": ("PlantDoc train (field-domain adaptation), split 80/20 for epoch "
                     "selection; PlantDoc test untouched and scored once at the end"),
        "source": "pratik kayal / PlantDoc-Dataset (Singh et al. 2019), MIT",
        "class_order": order,
        "counts": {"train_field": tr, "val_field": va, "test_field": te, "holdout_field": ho},
        "totals": {k: sum(v.values()) for k, v in
                   {"train_field": tr, "val_field": va, "test_field": te, "holdout_field": ho}.items()},
        "field_absent_classes": sorted(set(order) - set(tr) - set(va) - set(te)),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "split_meta.json").write_text(json.dumps(meta, indent=2))

    print(f"PlantDoc root: {pd_root}")
    for k, v in meta["totals"].items():
        print(f"  {k:16s} {v:5d} images / {len(meta['counts'][k])} classes")
    print(f"  (field-absent classes, never scored: {len(meta['field_absent_classes'])})")
    print(f"wrote {OUT / 'split_meta.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
