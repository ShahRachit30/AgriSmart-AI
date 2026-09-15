#!/usr/bin/env python3
"""Build the 38-class lab splits (`data/splits38/{train,val}`) from `data/raw/plantvillage38`.

Why a second split builder
--------------------------
`scripts/prepare_data.py` builds the original 18-class splits. The 38-class model needs
its own splits so class indices line up with the new checkpoint, and it needs a cap per
class: PlantVillage is very imbalanced (152 potato-healthy vs 5,507 orange HLB) and this
box has two CPU cores, so an epoch over all 54,303 images would take 25 minutes.

The split is stratified and deterministic (seed 42):
  * `val`   - `--val-per-class` (default 40) images per class, disjoint from train
  * `train` - up to `--train-per-class` (default 450) of the remainder, symlinked
    (the extracted JPEGs are used in place - no duplicated disk)

Class order is written to `model/class_names38.json` in **alphabetical** order, so the
index = label mapping is stable and easy to audit. Passing `--activate` also copies it
over `model/class_names.json`, which is what the app reads - only do that once the new
checkpoint is in place.

Usage
-----
    python scripts/build_pv38_splits.py                     # build the splits
    python scripts/build_pv38_splits.py --report            # print the plan, write nothing
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "plantvillage38"
OUT = ROOT / "data" / "splits38"
SEED = 42


def discover() -> dict[str, list[Path]]:
    if not SRC.is_dir():
        raise SystemExit(f"{SRC} missing - run scripts/extract_plantvillage38.py first")
    found: dict[str, list[Path]] = {}
    for folder in sorted(p for p in SRC.iterdir() if p.is_dir()):
        imgs = sorted(p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        if imgs:
            found[folder.name] = imgs
    if not found:
        raise SystemExit(f"no class folders with images under {SRC}")
    return found


def split_class(images: list[Path], val_per_class: int, train_per_class: int) -> tuple[list, list]:
    rng = random.Random(f"{SEED}:{images[0].parent.name}")
    shuffled = images[:]
    rng.shuffle(shuffled)
    val = sorted(shuffled[:val_per_class])
    train_pool = shuffled[val_per_class:]
    rng.shuffle(train_pool)
    train = sorted(train_pool[:train_per_class])
    return train, val


def link_or_copy(src: Path, dest: Path) -> None:
    if dest.exists():
        return
    try:
        dest.symlink_to(src)                     # cheap: the JPEGs stay where they are
    except OSError:
        shutil.copy2(src, dest)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--train-per-class", type=int, default=450,
                    help="cap on training images per class (CPU budget)")
    ap.add_argument("--val-per-class", type=int, default=40)
    ap.add_argument("--activate", action="store_true",
                    help="also write model/class_names.json (only when the model is trained)")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    classes = discover()
    order = sorted(classes)                       # alphabetical, deterministic
    plan, tot_train, tot_val = {}, 0, 0
    for slug in order:
        imgs = classes[slug]
        train, val = split_class(imgs, args.val_per_class, args.train_per_class)
        plan[slug] = {"available": len(imgs), "train": len(train), "val": len(val)}
        tot_train += len(train)
        tot_val += len(val)

    print(f"{len(order)} classes | available {sum(v['available'] for v in plan.values())} "
          f"| train {tot_train} | val {tot_val}")
    if args.report:
        for slug in order:
            p = plan[slug]
            print(f"  {slug:34s} available {p['available']:>5}  train {p['train']:>4}  val {p['val']:>3}")
        return 0

    for slug in order:
        imgs = classes[slug]
        train, val = split_class(imgs, args.val_per_class, args.train_per_class)
        for name, files in (("train", train), ("val", val)):
            folder = OUT / name / slug
            folder.mkdir(parents=True, exist_ok=True)
            for f in files:
                link_or_copy(f, folder / f.name)

    meta = {
        "n_classes": len(order), "order": order, "seed": SEED,
        "caps": {"train_per_class": args.train_per_class, "val_per_class": args.val_per_class},
        "counts": plan, "n_train": tot_train, "n_val": tot_val,
        "source": "data/raw/plantvillage38 (PlantVillage 38-class set; the source data behind "
                  "Kaggle's new-plant-diseases-dataset)",
    }
    (OUT / "split_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    staged = ROOT / "model" / "class_names38.json"
    classes_doc = {"order": order, "n_classes": len(order),
                   "source": "PlantVillage 38-class set", "built": f"seed {SEED}"}
    staged.write_text(json.dumps(classes_doc, indent=2) + "\n")
    print(f"\nwrote {OUT} (symlinks) and {staged.relative_to(ROOT)}")
    if args.activate:
        (ROOT / "model" / "class_names.json").write_text(json.dumps(classes_doc, indent=2) + "\n")
        print("activated: model/class_names.json now lists the 38 classes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
