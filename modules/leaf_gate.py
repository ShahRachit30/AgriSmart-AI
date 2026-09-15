"""Out-of-distribution gate: "is this photo even a leaf?"

Why this exists
---------------
A softmax classifier over the lab classes (18 in v1, 38 in v1.2) *always*
returns one of them - the gate itself is class-count agnostic.
Feed it a chair, a selfie or a screenshot and it answers "Late blight, 94 %" -
confidently wrong, which is worse for a farmer (and for a judge) than an honest
"this is not a leaf photo".

The gate is a small model in front of the classifier:

    upload -> [leaf gate] --not a leaf--> friendly retry message, no diagnosis
                        \\--leaf / unsure-> disease classifier + advisory

It is a frozen ImageNet MobileNetV3-small embedding plus a handful of cheap
colour/texture statistics, classified by a logistic regression trained on
PlantVillage + PlantDoc leaves vs Caltech101/SVHN non-leaves (see
`scripts/train_leaf_gate.py`, metrics in `report/gate_metrics.json`).

Policy (deliberately asymmetric - a wrongly rejected leaf costs a farmer a
re-upload; a wrongly accepted chair costs a wrong diagnosis):

    p_leaf <  threshold            -> reject, ask for a retake
    threshold <= p_leaf < soft     -> accept, but warn that the result may be shaky
    p_leaf >= soft                 -> accept silently

If `model/leaf_gate.joblib` is absent the module degrades to `available()=False`
and the API behaves exactly as before - the gate can never make the app worse.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "model" / "leaf_gate.joblib"
BACKBONE_PATH = ROOT / "model" / "mobilenet_v3_small_imagenet.pth"

_EMBED = None          # cached feature extractor
_LOADED = None         # cached gate payload
_LOAD_ERROR: str | None = None
THRESH = 0.35          # fallback defaults, overwritten by the trained file
THRESH_SOFT = 0.60


def _env_disabled() -> bool:
    """`AGRISMART_LEAF_GATE=off` disables the refusal.

    Only for callers that already know the subject (the upload-plumbing tests, which
    post synthetic non-photos, and batch jobs scoring a labelled leaf dataset). The
    app never sets it, so a farmer's photo is always gated.
    """
    return os.environ.get("AGRISMART_LEAF_GATE", "on").strip().lower() in {"off", "0", "false", "no"}


def available() -> bool:
    """Gate usable and enabled. Set AGRISMART_LEAF_GATE=off to disable (tests/batch)."""
    return GATE_PATH.exists() and not _env_disabled()


def status() -> dict[str, Any]:
    """Published on /api/health and /api/meta (never contains anything sensitive)."""
    if _env_disabled():
        return {"available": False, "reason": "disabled via AGRISMART_LEAF_GATE=off",
                "how_to_train": "unset the variable to re-enable the refusal"}
    payload = _load()
    if payload is None:
        return {"available": False, "reason": _LOAD_ERROR or "not trained yet",
                "how_to_train": "python scripts/train_leaf_gate.py"}
    metrics = payload.get("metrics", {})
    return {
        "available": True,
        "threshold": payload.get("threshold"),
        "threshold_uncertain": payload.get("threshold_soft"),
        "auc": metrics.get("auc"),
        "rejects_non_leaf_pct": round(100 * float(metrics.get("rejection_rate_non_leaves", 0)), 1),
        "rejects_real_leaf_pct": round(100 * float(metrics.get("false_rejection_rate_leaves", 0)), 2),
        "build": metrics.get("trained"),
    }


def handcrafted(pil_img) -> np.ndarray:
    """Cheap colour/texture statistics - they catch the obvious cases (a dark
    screenshot, a grey wall) even when the embedding is unsure."""
    import numpy as np
    from PIL import Image

    img = pil_img.convert("RGB").resize((128, 128), Image.BILINEAR)
    arr = np.asarray(img).astype(np.float32)
    hsv = np.asarray(img.convert("HSV")).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    green = ((h >= 45) & (h <= 125) & (s >= 45) & (v >= 35)).mean()
    green2 = (((g > r + 12) & (g > b + 12) & (g > 35))).mean()
    gray = (np.abs(r - g) + np.abs(g - b) + np.abs(r - b) / 2).mean()
    colourfulness = np.sqrt(arr[..., 0].std() ** 2 + arr[..., 1].std() ** 2 + arr[..., 2].std() ** 2)
    gy, gx = np.gradient(arr.mean(axis=2))
    edge = float(np.sqrt(gy ** 2 + gx ** 2).mean())
    return np.array([
        green, green2,
        s.mean() / 255.0, v.mean() / 255.0, s.std() / 255.0, v.std() / 255.0,
        float(gray) / 255.0, colourfulness / 255.0, edge / 255.0,
        float((v < 40).mean()), float((v > 235).mean()),
    ], dtype=np.float32)


def _load():
    global _LOADED, _LOAD_ERROR
    if _LOADED is not None or _LOAD_ERROR is not None:
        return _LOADED
    if not GATE_PATH.exists():
        _LOAD_ERROR = f"no gate at {GATE_PATH.name}"
        return None
    try:
        import joblib
        _LOADED = joblib.load(GATE_PATH)
    except Exception as exc:                                    # pragma: no cover
        _LOAD_ERROR = f"{type(exc).__name__}: {exc}"
        return None
    return _LOADED


def _embedder():
    global _EMBED, _LOAD_ERROR
    if _EMBED is not None:
        return _EMBED
    import torch
    import torch.nn as nn
    from torchvision import models

    net = models.mobilenet_v3_small(weights=None)
    if BACKBONE_PATH.exists():
        # shipped weights -> the gate works with no internet at all
        state = torch.load(BACKBONE_PATH, map_location="cpu")
        net.load_state_dict(state)
    else:                                                        # pragma: no cover
        net = models.mobilenet_v3_small(weights="DEFAULT")
    net.classifier = nn.Identity()
    net.eval()
    for p in net.parameters():
        p.requires_grad_(False)
    _EMBED = net
    return net


def features(pil_img) -> Any:
    """576-d embedding + the 11 handcrafted colour/texture statistics."""
    import numpy as np
    import torch
    from PIL import Image, ImageOps
    from torchvision import transforms

    rgb = ImageOps.exif_transpose(pil_img).convert("RGB")
    tf = transforms.Compose([
        transforms.Resize(int(160 * 1.14)), transforms.CenterCrop(160),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])
    with torch.no_grad():
        emb = _embedder()(tf(rgb)[None]).numpy()
    hand = handcrafted(rgb)[None]
    return np.concatenate([emb, hand], axis=1)


def check_pil(pil_img) -> dict[str, Any]:
    """Leaf gate verdict for a PIL image. Never raises."""
    payload = _load()
    if payload is None:
        return {"available": False, "verdict": "unknown", "p_leaf": None,
                "reason": _LOAD_ERROR}
    try:
        prob = float(payload["model"].predict_proba(features(pil_img))[0, 1])
    except Exception as exc:                                     # pragma: no cover
        return {"available": True, "verdict": "unknown", "p_leaf": None,
                "reason": f"{type(exc).__name__}: {exc}"}
    hard = float(payload.get("threshold", THRESH))
    soft = float(payload.get("threshold_soft", THRESH_SOFT))
    verdict = "not_leaf" if prob < hard else ("uncertain" if prob < soft else "leaf")
    return {"available": True, "p_leaf": round(prob, 4), "verdict": verdict,
            "threshold": round(hard, 3), "threshold_uncertain": round(soft, 3)}


def check_bytes(data: bytes) -> dict[str, Any]:
    """Same, from raw upload bytes (uses the app's shared decoder)."""
    if not available():
        return {"available": False, "verdict": "unknown", "p_leaf": None}
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        return {"available": True, "verdict": "unknown", "p_leaf": None,
                "reason": f"undecodable: {exc}"}
    return check_pil(img)


def is_leaf_or_unsure(verdict: str) -> bool:
    return verdict in ("leaf", "uncertain", "unknown")
