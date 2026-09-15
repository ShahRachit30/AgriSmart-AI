#!/usr/bin/env python3
"""Train the "is this even a leaf?" gate (out-of-distribution rejection).

The problem it fixes
--------------------
A softmax classifier over 18 leaf-disease classes always returns one of them at
high confidence - a chair, a selfie or a screenshot is reported as "Late blight
94 %". That is the single most damaging demo failure: the model looks like it is
guessing. The fix is not a bigger classifier, it is a cheap *gate* in front:

    photo -> [leaf gate] --not a leaf--> friendly "retake the photo" answer
                        \\--leaf--------> disease classifier + advisory

How it is built
---------------
* features : frozen ImageNet MobileNetV3-small embedding (576-d) + a few
             colour/texture statistics that are cheap and hard to fake
             (green-pixel fraction, saturation/value means, edge density,
             colourfulness, dark/bright fractions)
* classifier: logistic regression, class-balanced, on ~5 k leaf photos
             (PlantVillage lab + PlantDoc field, both domains, all 18 classes)
             vs ~11 k non-leaf photos (Caltech101 objects/faces/indoor +
             SVHN screenshots - i.e. the things people actually upload by
             accident)
* negatives used for the *test* split come from sources the classifier never
  trains on (CIFAR-100 objects + a held-out SVHN slice), so the reported
  rejection rate is not self-congratulation.

Threshold policy: reject only when the gate is confident, because a wrongly
rejected real leaf costs a farmer a re-upload while a wrongly accepted chair
costs a wrong diagnosis. Concretely we pick the lowest threshold whose
false-rejection rate on held-out leaf photos is <= 2 %, and add a soft band
("this does not look like a clear leaf photo - results may be unreliable")
that still runs the classifier.

Usage
-----
    python scripts/train_leaf_gate.py                  # ~6 min on 2 CPU cores
    python scripts/train_leaf_gate.py --negatives 4000
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
PV = ROOT / "data" / "raw" / "plantvillage"
PD = ROOT / "data" / "raw" / "plantdoc"
FIELD = ROOT / "data" / "splits_field"
NEG_ROOT = ROOT / "data" / "raw" / "negatives"
OUT_JOBLIB = ROOT / "model" / "leaf_gate.joblib"
OUT_META = ROOT / "report" / "gate_metrics.json"


# --------------------------------------------------------------- feature model
def build_feature_net():
    """Frozen ImageNet MobileNetV3-small that returns a 576-d embedding."""
    import torch
    import torch.nn as nn
    from torchvision import models

    net = models.mobilenet_v3_small(weights="DEFAULT")
    net.classifier = nn.Identity()          # keep the pooled features
    net.eval()
    for p in net.parameters():
        p.requires_grad_(False)
    return net


CACHE = ROOT / "data" / "tmp" / "gate_cache"


from modules.leaf_gate import handcrafted  # noqa: E402  (single source of truth)


def embed(paths, batch=48, threads=2, tag: str | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Embedding + handcrafted features for a list of image paths.

    `tag` writes the result to data/tmp/gate_cache so a recycled sandbox (or a
    re-run) does not have to redo the forward passes - this box can restart at
    any moment, and a wasted 5 minutes is a real cost.
    """
    if tag:
        CACHE.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in tag)
        key = f"{safe}_{len(paths)}"
        e_f, h_f = CACHE / f"{key}_emb.npy", CACHE / f"{key}_hand.npy"
        if e_f.exists() and h_f.exists():
            print(f"   {tag}: cached ({len(paths)})", flush=True)
            return np.load(e_f), np.load(h_f)
        result = _embed_uncached(paths, batch, threads)
        np.save(e_f, result[0]); np.save(h_f, result[1])
        return result
    return _embed_uncached(paths, batch, threads)


def _embed_uncached(paths, batch=48, threads=2) -> tuple[np.ndarray, np.ndarray]:
    import torch
    from PIL import Image, ImageOps
    from torchvision import transforms

    torch.set_num_threads(threads)
    net = build_feature_net()
    tf = transforms.Compose([
        transforms.Resize(int(160 * 1.14)), transforms.CenterCrop(160),
        transforms.ToTensor(), transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])
    embs, hand = [], []
    t0 = time.time()
    with torch.no_grad():
        for i in range(0, len(paths), batch):
            chunk = paths[i:i + batch]
            tensors, hc = [], []
            for p in chunk:
                try:
                    img = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
                except Exception:
                    img = Image.new("RGB", (160, 160), (128, 128, 128))
                tensors.append(tf(img))
                hc.append(handcrafted(img))
            embs.append(net(torch.stack(tensors)).numpy())
            hand.append(np.stack(hc))
            if (i // batch) % 20 == 0:
                done = min(i + batch, len(paths))
                print(f"   {done}/{len(paths)} ({time.time() - t0:.0f}s)", flush=True)
    return np.concatenate(embs).astype(np.float32), np.concatenate(hand).astype(np.float32)


# ------------------------------------------------------------------- leaf lists
def leaves() -> tuple[list[Path], list[Path]]:
    """(lab leaves, field leaves) - both are leaves, so both are positives."""
    lab = [p for d in sorted(PV.iterdir()) if d.is_dir()
           for p in sorted(d.iterdir()) if p.suffix.lower() in IMG_EXTS]
    field = []
    for split in ("train", "test"):
        root = PD / split
        if root.is_dir():
            field += [p for d in sorted(root.rglob("*")) if d.is_dir()
                      for p in sorted(d.iterdir()) if p.suffix.lower() in IMG_EXTS]
    return lab, field


def _paths_from_dataset(ds, root_hint: Path | None = None) -> list[Path]:
    """Robustly list the image files behind a torchvision dataset, across versions."""
    for attr in ("_images", "samples", "index", "_flat_imgs", "imgs"):
        v = getattr(ds, attr, None)
        if not isinstance(v, (list, tuple)) or not v:
            continue
        first = v[0]
        try:
            if isinstance(first, (str, Path)):
                return [Path(x) for x in v if Path(x).exists()]
            if isinstance(first, dict) and "path" in first:
                return [Path(x["path"]) for x in v]
            if isinstance(first, (list, tuple)) and len(first) >= 1 and isinstance(first[0], (str, Path)):
                return [Path(x[0]) for x in v if Path(x[0]).exists()]
        except Exception:
            continue
    root = Path(root_hint or getattr(ds, "root", NEG_ROOT))
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in IMG_EXTS)


def download_negatives() -> dict[str, list[Path]]:
    """Three real-photo negative sources, cheap to fetch and realistic.

    caltech101  objects, faces, indoor scenes (what a judge uploads by accident)
    svhn        phone-photo crops of house numbers -> stands in for screenshots/text
    pets        held-out source: cats and dogs, never used for training the gate
    """
    from PIL import Image
    from torchvision import datasets

    NEG_ROOT.mkdir(parents=True, exist_ok=True)
    out: dict[str, list[Path]] = {}

    try:
        ds = datasets.Caltech101(str(NEG_ROOT), download=True)
        out["caltech101"] = _paths_from_dataset(ds, NEG_ROOT / "caltech101")
        print(f"   caltech101 : {len(out['caltech101'])}", flush=True)
    except Exception as exc:
        print(f"   caltech101 unavailable: {type(exc).__name__}: {exc}", flush=True)

    try:
        ds = datasets.SVHN(str(NEG_ROOT), split="train", download=True)
        d = NEG_ROOT / "svhn_dump"
        d.mkdir(exist_ok=True)
        raw = ds.data                      # list[PIL.Image] on new, ndarray on old
        out["svhn"] = []
        for i in range(0, len(raw), 15):   # ~4.9 k spread over the split
            f = d / f"svhn_{i:06d}.jpg"
            if not f.exists():
                item = raw[i]
                if hasattr(item, "save"):                    # newer: PIL.Image
                    img = item
                else:
                    arr = np.asarray(item)
                    if arr.ndim == 3 and arr.shape[0] in (1, 3):   # older: CHW
                        arr = arr.transpose(1, 2, 0)
                    img = Image.fromarray(arr)
                img.convert("RGB").resize((96, 96), Image.BICUBIC).save(f, quality=92)
            out["svhn"].append(f)
        print(f"   svhn       : {len(out['svhn'])}", flush=True)
    except Exception as exc:
        print(f"   svhn unavailable: {type(exc).__name__}: {exc}", flush=True)

    try:
        ds = datasets.OxfordIIITPet(str(NEG_ROOT), split="test", download=True)
        out["pets"] = _paths_from_dataset(ds, NEG_ROOT / "oxford-iiit-pet")
        print(f"   pets(test) : {len(out['pets'])}  <- unseen negative source", flush=True)
    except Exception as exc:
        print(f"   pets unavailable: {type(exc).__name__}: {exc}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lab-leaves", type=int, default=3500)
    ap.add_argument("--negatives", type=int, default=9000)
    ap.add_argument("--max-frr", type=float, default=0.02,
                    help="largest tolerated false-rejection rate on real leaf photos")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()

    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    rng = random.Random(a.seed)
    lab, field = leaves()
    print(f"leaves: {len(lab)} lab (PlantVillage) + {len(field)} field (PlantDoc)", flush=True)
    rng.shuffle(lab)
    lab = lab[:a.lab_leaves]

    neg = download_negatives()
    caltech = list(neg.get("caltech101", []))
    svhn = list(neg.get("svhn", []))
    pets = list(neg.get("pets", []))
    for lst in (caltech, svhn, pets):
        rng.shuffle(lst)

    # ---- split. NOTE: the negative TEST sources (pets + half of SVHN) are never
    #      used for training, so the rejection rate is measured on unseen object
    #      types rather than on memorised ones.
    n_half = len(svhn) // 2
    neg_train = caltech + svhn[:n_half]
    neg_test = pets + svhn[n_half:]
    rng.shuffle(neg_train)
    rng.shuffle(neg_test)

    n_neg = min(a.negatives, len(neg_train))
    neg_train = neg_train[:n_neg]
    neg_test = neg_test[:max(1500, min(len(neg_test), 6000))]

    # leaf split: lab and FIELD leaves must both survive, so test on a mix of both
    n_field_test = min(400, len(field) // 3)
    field_test, field_train = field[:n_field_test], field[n_field_test:]
    n_lab_test = min(600, len(lab) // 4)
    lab_test, lab_train = lab[:n_lab_test], lab[n_lab_test:]

    print(f"train: {len(lab_train) + len(field_train)} leaves vs {len(neg_train)} non-leaves",
          flush=True)
    print(f"test : {len(lab_test) + len(field_test)} leaves vs {len(neg_test)} non-leaves",
          flush=True)

    def embed_all(paths, tag):
        print(f"  embedding {tag} ({len(paths)})", flush=True)
        return embed(paths, threads=a.threads, tag=tag)

    e_lab_tr, h_lab_tr = embed_all(lab_train, "lab leaves/train")
    e_fd_tr, h_fd_tr = embed_all(field_train, "field leaves/train")
    e_neg_tr, h_neg_tr = embed_all(neg_train, "non-leaves/train")
    e_lab_te, h_lab_te = embed_all(lab_test, "lab leaves/test")
    e_fd_te, h_fd_te = embed_all(field_test, "field leaves/test")
    e_neg_te, h_neg_te = embed_all(neg_test, "non-leaves/test")

    def stack(e, h):
        return np.concatenate([e, h], axis=1)

    X = np.concatenate([stack(e_lab_tr, h_lab_tr), stack(e_fd_tr, h_fd_tr),
                        stack(e_neg_tr, h_neg_tr)])
    y = np.array([1] * (len(e_lab_tr) + len(e_fd_tr)) + [0] * len(e_neg_tr))
    order = np.random.RandomState(a.seed).permutation(len(y))
    X, y = X[order], y[order]

    Xt_leaf = np.concatenate([stack(e_lab_te, h_lab_te), stack(e_fd_te, h_fd_te)])
    yt_leaf = np.ones(len(Xt_leaf))
    Xt_neg = stack(e_neg_te, h_neg_te)
    yt_neg = np.zeros(len(Xt_neg))

    clf = make_pipeline(StandardScaler(),
                        LogisticRegression(max_iter=3000, C=0.5, class_weight="balanced"))
    t0 = time.time()
    clf.fit(X, y)
    print(f"  trained in {time.time() - t0:.1f}s", flush=True)

    p_leaf = clf.predict_proba(Xt_leaf)[:, 1]
    p_neg = clf.predict_proba(Xt_neg)[:, 1]
    auc = roc_auc_score(np.r_[yt_leaf, yt_neg], np.r_[p_leaf, p_neg])

    # threshold: the lowest cut-off whose false-rejection rate on real leaves is
    # inside budget (a wrongly rejected leaf is the expensive error)
    thresh = 0.5
    for t in np.arange(0.05, 0.96, 0.01):
        frr = float((p_leaf < t).mean())
        if frr <= a.max_frr:
            thresh = float(round(t, 2))
            break
    frr = float((p_leaf < thresh).mean())
    fnr = float((p_neg > thresh).mean())
    soft = float(min(0.75, thresh + 0.25))          # "uncertain" band starts here

    by_source = {}
    for name, lo, hi in (("field_leaves_plantdoc", len(e_lab_te), len(Xt_leaf)),
                         ("lab_leaves_plantvillage", 0, len(e_lab_te))):
        by_source[name] = {"n": hi - lo, "rejected": float((p_leaf[lo:hi] < thresh).mean())}

    metrics = {
        "auc": round(float(auc), 4),
        "threshold_not_leaf": thresh,
        "threshold_uncertain": soft,
        "false_rejection_rate_leaves": round(frr, 4),
        "rejection_rate_non_leaves": round(1 - fnr, 4),
        "n_train": {"leaves": int((y == 1).sum()), "non_leaves": int((y == 0).sum())},
        "n_test": {"leaves_lab": len(e_lab_te), "leaves_field": len(e_fd_te),
                   "non_leaves_unseen_sources": len(Xt_neg)},
        "per_source": by_source,
        "feature": "mobilenet_v3_small(ImageNet, frozen) 576-d + 11 colour/texture stats",
        "trained": time.strftime("%Y-%m-%d %H:%M"),
        "leaf_sources": "PlantVillage (lab) + PlantDoc train/test (field)",
        "non_leaf_sources_train": "Caltech101 (objects/faces/indoor), SVHN (first half)",
        "non_leaf_sources_test": "Oxford-IIIT Pet test (cats/dogs) + SVHN second half - neither used in training",
    }

    OUT_JOBLIB.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf, "threshold": thresh, "threshold_soft": soft,
                 "metrics": metrics}, OUT_JOBLIB)
    OUT_META.write_text(json.dumps(metrics, indent=2))

    print("\n=== leaf gate ===")
    print(f"  AUC                    {auc:.4f}")
    print(f"  threshold (not a leaf) {thresh}   [uncertain from {soft}]")
    print(f"  real leaves rejected   {frr * 100:.2f} %  (budget {a.max_frr * 100:.0f} %)")
    print(f"  non-leaves rejected    {(1 - fnr) * 100:.1f} % (unseen sources)")
    print(f"  saved -> {OUT_JOBLIB.name} ({OUT_JOBLIB.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
