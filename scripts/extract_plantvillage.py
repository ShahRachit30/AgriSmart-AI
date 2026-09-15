#!/usr/bin/env python3
"""Extract the 18 AgriSmart classes from the PlantVillage parquet mirror.

The mirror labels images with an integer `label` column whose ordering is *not*
documented in the dataset card. The mapping below was identified empirically in
the original build (labelled contact sheet + per-class count cross-check) and is
treated as **verified data** by CONTINUE_HERE.md section 3.

Output layout (ImageFolder compatible):
    data/raw/plantvillage/<slug>/<slug>_<n>.jpg

Usage
-----
    python scripts/extract_plantvillage.py                 # all shards, max side 512
    python scripts/extract_plantvillage.py --max-side 0     # keep original bytes
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARQUET_DIR = ROOT / "data" / "raw" / "plantvillage_parquet"
OUT_DIR = ROOT / "data" / "raw" / "plantvillage"

# label int -> slug.  VERIFIED mapping (see CONTINUE_HERE.md section 3).
TARGETS: dict[int, str] = {
    0: "apple_scab",
    1: "apple_black_rot",
    3: "apple_healthy",
    7: "corn_grey_leaf_spot",
    8: "corn_common_rust",
    9: "corn_healthy",
    11: "grape_black_rot",
    13: "grape_healthy",
    18: "bell_pepper_bacterial_spot",
    19: "bell_pepper_healthy",
    20: "potato_early_blight",
    21: "potato_healthy",
    22: "potato_late_blight",
    28: "tomato_bacterial_spot",
    29: "tomato_early_blight",
    30: "tomato_healthy",
    31: "tomato_late_blight",
    32: "tomato_leaf_mold",
}


def _pick_columns(names: list[str]) -> tuple[str, str]:
    """Find the (image, label) columns without hard-coding the mirror schema."""
    img = next((n for n in names if "image" in n.lower() or "img" in n.lower()), None)
    lab = next((n for n in names if "label" in n.lower()), None)
    if img is None or lab is None:
        raise SystemExit(f"could not locate image/label columns in {names}")
    return img, lab


def _to_bytes(value) -> bytes | None:
    """Accept bytes | {"bytes":..,"path":..} | PIL image | raw str path."""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, dict):
        b = value.get("bytes") or value.get("data")
        if b:
            return _to_bytes(b)
        p = value.get("path")
        if p and Path(p).exists():
            return Path(p).read_bytes()
        return None
    if hasattr(value, "save"):  # PIL.Image
        buf = io.BytesIO()
        value.convert("RGB").save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    if isinstance(value, str) and Path(value).exists():
        return Path(value).read_bytes()
    return None


def extract(max_side: int = 512, limit_per_class: int = 0) -> dict:
    import pyarrow.parquet as pq
    from PIL import Image

    shards = sorted(PARQUET_DIR.glob("*.parquet"))
    if not shards:
        raise SystemExit(f"no parquet shards in {PARQUET_DIR} - run scripts/download_datasets.py")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("scanning shard 0 for schema ...")
    pf0 = pq.ParquetFile(shards[0])
    names = list(pf0.schema_arrow.names)
    img_col, lab_col = _pick_columns(names)
    print(f"  columns={names} -> image='{img_col}' label='{lab_col}'")

    counts: dict[str, int] = {s: 0 for s in TARGETS.values()}
    per_class_n: dict[int, int] = {}
    written = 0
    for si, shard in enumerate(shards):
        pf = pq.ParquetFile(shard)
        for batch in pf.iter_batches(batch_size=96, columns=[img_col, lab_col]):
            labels = batch.column(lab_col).to_pylist()
            images = batch.column(img_col).to_pylist()
            for lab_raw, im_raw in zip(labels, images):
                try:
                    lab = int(lab_raw)
                except (TypeError, ValueError):
                    continue
                slug = TARGETS.get(lab)
                if slug is None:
                    continue
                per_class_n[lab] = per_class_n.get(lab, 0) + 1
                if limit_per_class and per_class_n[lab] > limit_per_class:
                    continue
                data = _to_bytes(im_raw)
                if not data:
                    continue
                try:
                    im = Image.open(io.BytesIO(data)).convert("RGB")
                except Exception:
                    continue
                if max_side and max(im.size) > max_side:
                    im.thumbnail((max_side, max_side), Image.BICUBIC)
                n = counts[slug]
                class_dir = OUT_DIR / slug
                class_dir.mkdir(parents=True, exist_ok=True)
                im.save(class_dir / f"{slug}_{n:05d}.jpg", format="JPEG", quality=92)
                counts[slug] += 1
                written += 1
        print(f"  shard {si + 1}/{len(shards)} done -> {written} images written", flush=True)

    meta = {
        "label_to_slug": {str(k): v for k, v in TARGETS.items()},
        "counts": counts,
        "total": written,
        "source": "dpdl-benchmark/plant_village (CC-BY)",
    }
    (OUT_DIR / "_extract_meta.json").write_text(json.dumps(meta, indent=2))
    print("\nper-class counts:")
    for slug, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {slug:32s} {n:5d}")
    print(f"TOTAL {written}")
    missing = [s for s, n in counts.items() if n == 0]
    if missing:
        print(f"WARNING zero images for: {missing}")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-side", type=int, default=512, help="downscale longest side (0=keep)")
    ap.add_argument("--limit-per-class", type=int, default=0, help="stop after N/class (0=all)")
    a = ap.parse_args()
    extract(max_side=a.max_side, limit_per_class=a.limit_per_class)
    return 0


if __name__ == "__main__":
    sys.exit(main())
