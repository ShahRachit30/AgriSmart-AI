#!/usr/bin/env python3
"""Re-fetch every dataset used by AgriSmart AI (idempotent, resumable-ish).

Sources / licences
------------------
* PlantVillage (lab train+val)  : HuggingFace mirror `dpdl-benchmark/plant_village`
                                  (Hughes & Salathe 2015) -- CC-BY
                                  13 parquet shards, ~6.3 GB -> data/raw/plantvillage_parquet/
* PlantDoc   (held-out field)   : github.com/pratikkayal/PlantDoc-Dataset (Singh et al. 2019)
                                  master tarball ~984 MB -> data/raw/plantdoc/
* Crop recommendation (Bonus A) : HuggingFace mirror `randalakab/Crop-recommendation`
                                  (Atharva Ingle, Kaggle) -- CC0 -> data/raw/crop_recommendation.csv

Usage
-----
    python scripts/download_datasets.py                # everything
    python scripts/download_datasets.py --only crops   # plantvillage | plantdoc | crops
Files already present with the expected size are skipped, so re-running is cheap.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TMP = ROOT / "data" / "tmp"

PV_REPO = "dpdl-benchmark/plant_village"
PV_BASE = f"https://huggingface.co/datasets/{PV_REPO}/resolve/main/data"
PV_SHARDS = [f"train-{i:05d}-of-00013.parquet" for i in range(13)]

PLANTDOC_URL = "https://codeload.github.com/pratikkayal/PlantDoc-Dataset/tar.gz/refs/heads/master"
CROP_CSV_URL = "https://huggingface.co/datasets/randalakab/Crop-recommendation/resolve/main/crop_recommendation.csv"

CHUNK = 1 << 20  # 1 MiB


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:,.1f} TB"


def fetch(url: str, dest: Path, expect_bytes: int | None = None, label: str = "") -> Path:
    """Stream `url` -> `dest`. Skips when the file already looks complete."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    label = label or dest.name
    if dest.exists():
        size = dest.stat().st_size
        if expect_bytes is None or size == expect_bytes:
            print(f"  [skip] {label} already present ({human(size)})")
            return dest
        print(f"  [redo] {label} size {human(size)} != expected {human(expect_bytes)}")
    part = dest.with_suffix(dest.suffix + ".part")
    t0 = time.time()
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or expect_bytes or 0)
        done = 0
        last = 0.0
        with open(part, "wb") as fh:
            for chunk in r.iter_content(CHUNK):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                now = time.time()
                if now - last > 5:
                    last = now
                    pct = f"{100 * done / total:5.1f}%" if total else "  ?  "
                    rate = done / max(now - t0, 1e-6)
                    print(f"    {label}: {pct} {human(done)} @ {human(rate)}/s", flush=True)
    part.replace(dest)
    print(f"  [ok]   {label} {human(dest.stat().st_size)} in {time.time() - t0:.0f}s")
    return dest


# --------------------------------------------------------------------------- #
def get_plantvillage() -> None:
    out = RAW / "plantvillage_parquet"
    out.mkdir(parents=True, exist_ok=True)
    print(f"[1/3] PlantVillage parquet shards -> {out}")
    for shard in PV_SHARDS:
        fetch(f"{PV_BASE}/{shard}", out / shard, expect_bytes=None, label=shard)


def get_plantdoc() -> None:
    out = RAW / "plantdoc"
    tar = TMP / "plantdoc.tar.gz"
    print(f"[2/3] PlantDoc -> {out}")
    if out.exists() and any(out.glob("*/**/*.jpg")):
        n = sum(1 for _ in out.rglob("*.jpg"))
        print(f"  [skip] PlantDoc already extracted ({n} jpg)")
        return
    fetch(PLANTDOC_URL, tar, label="plantdoc.tar.gz")
    print("  extracting ...", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar) as tf:
        members = tf.getmembers()
        roots = {m.name.split("/")[0] for m in members}
        strip = next(iter(roots)) + "/" if len(roots) == 1 else ""
        for m in members:
            if not m.name.startswith(strip):
                continue
            m.name = m.name[len(strip):]
            if m.name:
                tf.extractall(out, members=[m]) if m.isfile() or m.isdir() else None
    n = sum(1 for _ in out.rglob("*.jpg"))
    print(f"  [ok]   extracted {n} jpg")
    tar.unlink(missing_ok=True)


def get_crops() -> None:
    dest = RAW / "crop_recommendation.csv"
    print(f"[3/3] Crop recommendation CSV -> {dest}")
    fetch(CROP_CSV_URL, dest, label="crop_recommendation.csv")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", choices=["plantvillage", "plantdoc", "crops"], default=None)
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    jobs = {"plantvillage": get_plantvillage, "plantdoc": get_plantdoc, "crops": get_crops}
    for name, fn in jobs.items():
        if a.only in (None, name):
            fn()
    print("\nAll requested datasets are present. Next: python scripts/extract_plantvillage.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
