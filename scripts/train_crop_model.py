#!/usr/bin/env python3
"""Train Bonus-A crop-recommendation model (RandomForest, 22 crops).

Data : data/raw/crop_recommendation.csv  (Kaggle "Crop Recommendation Dataset",
       Atharva Ingle, mirrored on HF as randalakab/Crop-recommendation, CC0)
Artifacts
    model/crop_model.joblib          RandomForest (200 trees, seed 42)
    model/crop_label_encoder.joblib  sklearn LabelEncoder
    report/crop_metrics.json         accuracy / macro-F1 / per-class support
Usage
    python scripts/train_crop_model.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "raw" / "crop_recommendation.csv"
FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


def main() -> int:
    if not CSV.exists():
        print(f"missing {CSV} - run scripts/download_datasets.py --only crops")
        return 1
    df = pd.read_csv(CSV)
    # the mirror ships lowercase headers (n, p, k, ...) - normalise to our canonical names
    rename = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=rename)
    canonical = {f.lower(): f for f in FEATURES}
    df = df.rename(columns={k: canonical[k] for k in df.columns if k in canonical})
    missing = [c for c in FEATURES + ["label"] if c not in df.columns]
    if missing:
        print(f"unexpected columns {list(df.columns)} (missing {missing})")
        return 1

    X = df[FEATURES].astype(float).values
    le = LabelEncoder()
    y = le.fit_transform(df["label"].astype(str))
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    clf = RandomForestClassifier(
        n_estimators=200, max_depth=None, min_samples_leaf=1,
        n_jobs=-1, random_state=42, class_weight="balanced_subsample",
    )
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)

    acc = float(accuracy_score(yte, pred))
    mf1 = float(f1_score(yte, pred, average="macro"))
    rep = classification_report(yte, pred, target_names=list(le.classes_), output_dict=True, zero_division=0)
    MODEL_DIR = ROOT / "model"
    REPORT = ROOT / "report"
    MODEL_DIR.mkdir(exist_ok=True)
    REPORT.mkdir(exist_ok=True)
    joblib.dump(clf, MODEL_DIR / "crop_model.joblib")
    joblib.dump(le, MODEL_DIR / "crop_label_encoder.joblib")

    imp = sorted(zip(FEATURES, clf.feature_importances_), key=lambda kv: -kv[1])
    out = {
        "model": "RandomForestClassifier(n_estimators=200, random_state=42)",
        "dataset": "crop_recommendation.csv (CC0) - 2200 rows, 22 crops",
        "features": FEATURES,
        "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
        "accuracy": acc, "macro_f1": mf1,
        "feature_importance": {k: round(float(v), 4) for k, v in imp},
        "per_class": {k: {m: round(float(v), 4) for m, v in vals.items()}
                      for k, vals in rep.items() if isinstance(vals, dict)},
        "seed": 42,
    }
    (REPORT / "crop_metrics.json").write_text(json.dumps(out, indent=2))

    # ---- also export an ONNX-free portable fallback: class centroid table ---- #
    cents = {cls: np.mean(X[y == i], axis=0).round(3).tolist() for i, cls in enumerate(le.classes_)}
    (MODEL_DIR / "crop_centroids.json").write_text(json.dumps(cents, indent=2))

    print(f"accuracy {acc:.4f} | macro-F1 {mf1:.4f} | train {len(Xtr)} test {len(Xte)}")
    print("top features:", ", ".join(f"{k}={v:.3f}" for k, v in imp[:4]))
    print(f"wrote {MODEL_DIR / 'crop_model.joblib'} and {REPORT / 'crop_metrics.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
