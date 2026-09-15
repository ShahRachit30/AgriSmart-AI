#!/usr/bin/env python3
"""Rebuild tests/fixtures/non_leaf - real object photos the leaf gate must refuse.

Why these files exist
---------------------
`modules/leaf_gate.py` refuses photos that are not leaves (a chair, a screenshot, an
animal) instead of inventing a diagnosis. `tests/test_leaf_gate.py` pins that promise
with real photographs, so the fixture cannot be synthetic - a generated grey square
would not exercise the same features a phone photo does.

The workspace wipes this folder on every revert (it lives outside the tracked code
path), which used to turn 12 green tests red with
`FileNotFoundError: .../tests/fixtures/non_leaf`. Run this to restore them.

Source: Caltech-101 (public, ~137 MB, downloaded once into data/raw/negatives).
Nine photos across chairs, animals, vehicles and household objects - none of them
remotely leaf-like, so a refusal is the only correct answer.

Usage:
    python3 scripts/make_non_leaf_fixtures.py            # download + export 9 photos
    python3 scripts/make_non_leaf_fixtures.py --check    # only report what is there
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "non_leaf"
DATA = Path("/var/tmp/agrismart-data/raw/negatives")

# Categories that share no visual vocabulary with a leaf.
WANTED = ["chair", "butterfly", "face", "Motorbikes", "airplanes", "car_side",
          "laptop", "watch", "Leopards"]
PER_CATEGORY = 1


def export_from(root: Path) -> int:
    """Copy one photo per wanted category out of an extracted Caltech-101 tree."""
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for category in WANTED:
        candidates = sorted(root.glob(f"{category}/*.jpg")) + sorted(root.glob(f"{category}/*.png"))
        for src in candidates[:PER_CATEGORY]:
            dest = OUT / f"{category.lower().replace('_', '')}_{src.name}"
            shutil.copy2(src, dest)
            print(f"   + {dest.name}  ({dest.stat().st_size // 1024} KB)")
            written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report the fixture state and exit")
    args = ap.parse_args()

    have = sorted(OUT.glob("*.jp*g")) if OUT.is_dir() else []
    if args.check:
        print(f"tests/fixtures/non_leaf: {len(have)} photo(s)")
        for f in have:
            print(f"   {f.name}")
        return 0 if len(have) >= 5 else 1

    if len(have) >= 5:
        print(f"already present: {len(have)} photos in {OUT.relative_to(ROOT)} - nothing to do")
        return 0

    # 1. an already-extracted tree is the fastest path
    existing = list(DATA.glob("**/101_ObjectCategories"))
    if not existing:
        existing = list(Path("/var/tmp").glob("**/101_ObjectCategories"))
    if existing:
        print(f"==> found an extracted Caltech-101 tree at {existing[0]}")
        n = export_from(existing[0])
        print(f"\nrestored {n} non-leaf fixture(s) from the local copy")
        return 0 if n >= 5 else 1

    # 2. otherwise download it once (public mirror, ~137 MB)
    print("==> no local copy - downloading Caltech-101 (public, ~137 MB, one time)")
    DATA.mkdir(parents=True, exist_ok=True)
    try:
        from torchvision.datasets import Caltech101
    except Exception as exc:  # pragma: no cover - environment problem
        print(f"!! torchvision unavailable ({exc}). Cannot restore the fixtures.")
        print("   Install it with: pip install torch torchvision --index-url "
              "https://download.pytorch.org/whl/cpu")
        return 2
    try:
        Caltech101(root=str(DATA), download=True)
    except Exception as exc:  # pragma: no cover - network problem
        print(f"!! download failed ({exc}).")
        return 2

    roots = list(DATA.glob("**/101_ObjectCategories")) or [DATA]
    n = export_from(roots[0])
    print(f"\nrestored {n} non-leaf fixture(s)")
    return 0 if n >= 5 else 1


if __name__ == "__main__":
    sys.exit(main())
