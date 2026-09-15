"""Load the trained classifier once and predict.

Public API
----------
    from model.inference import DiseaseClassifier
    clf = DiseaseClassifier()            # finds model/best_model.pth
    clf.available                        # False -> API returns a friendly 503
    clf.predict("leaf.jpg")              # -> dict (see below)
    clf.predict_pil(pil_image)

Returned dict
-------------
    {"class", "crop", "condition", "code", "healthy", "confidence",
     "top3": [{"class","crop","condition","confidence"}], "img_size", "model_name",
     "inference_ms", "advisory": ...}

The class list is always read from the checkpoint, so a re-trained model cannot
desync from `class_names.json`.
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CKPT = ROOT / "model" / "best_model.pth"
META_PATH = ROOT / "model" / "class_names.json"
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

_DISPLAY: dict[str, dict[str, Any]] = {}
if META_PATH.exists():
    try:
        _DISPLAY = json.loads(META_PATH.read_text()).get("display", {})
    except Exception:
        _DISPLAY = {}


def display_for(slug: str) -> dict[str, Any]:
    """Human label for a class slug ('tomato_late_blight' -> Tomato / Late Blight)."""
    if slug in _DISPLAY:
        return dict(_DISPLAY[slug])
    parts = slug.split("_")
    if parts and parts[-1] == "healthy":
        crop = " ".join(parts[:-1]).title()
        return {"crop": crop, "condition": "Healthy", "code": slug[:7].upper(), "healthy": True}
    return {"crop": parts[0].title() if parts else slug, "condition": " ".join(parts[1:]).title(),
            "code": slug[:7].upper(), "healthy": False}


class DiseaseClassifier:
    """Thin, dependency-light wrapper around the checkpoint."""

    def __init__(self, checkpoint: str | Path = DEFAULT_CKPT, device: str | None = None):
        self.checkpoint = Path(checkpoint)
        self.device = device
        self.model = None
        self.classes: list[str] = []
        self.img_size = 224
        self.model_name = "unknown"
        self.val_macro_f1: float | None = None
        self.load_error: str | None = None
        self.loaded_at: float | None = None
        self._transform = None
        self.load()

    # ------------------------------------------------------------------ #
    def load(self) -> bool:
        try:
            import torch  # noqa: F401
        except Exception as exc:  # torch missing entirely
            self.load_error = f"PyTorch not installed ({exc})"
            return False
        if not self.checkpoint.exists():
            self.load_error = (f"checkpoint not found at {self.checkpoint}. Train it with "
                               f"`python model/train.py --data data/splits --model resnet18 "
                               f"--img-size 192 --epochs 8 --batch-size 64`.")
            return False
        try:
            import torch
            from model.dataset import build_transforms
            from model.train import build_model

            device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
            ckpt = torch.load(self.checkpoint, map_location=device, weights_only=False)
            classes = list(ckpt.get("classes") or [])
            if not classes:
                raise ValueError("checkpoint has no class list")
            model = build_model(ckpt.get("model_name", "resnet18"), len(classes), pretrained=False)
            model.load_state_dict(ckpt["state_dict"])
            model.eval().to(device)
            self.model, self.classes = model, classes
            self.img_size = int(ckpt.get("img_size", 224))
            self.model_name = ckpt.get("model_name", "resnet18")
            self.val_macro_f1 = ckpt.get("val_macro_f1")
            self.device = device
            self._transform = build_transforms(self.img_size, train=False)
            self.loaded_at = time.time()
            self.load_error = None
            return True
        except Exception as exc:
            self.load_error = f"could not load checkpoint: {type(exc).__name__}: {exc}"
            return False

    @property
    def available(self) -> bool:
        return self.model is not None

    def info(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "checkpoint": str(self.checkpoint),
            "model_name": self.model_name,
            "img_size": self.img_size,
            "n_classes": len(self.classes),
            "classes": self.classes,
            "val_macro_f1": self.val_macro_f1,
            "device": self.device,
            "error": self.load_error,
        }

    # ------------------------------------------------------------------ #
    def _predict_tensor(self, pil_img, tta: bool = True, ensemble: bool = True) -> dict[str, Any]:
        """Softmax over one or more views of the leaf.

        The default decoding (`tta=True, ensemble=True`) is the strategy that won
        the held-out field split in `model/evaluate.py`: average the softmax of the
        centre-cropped view and the leaf-cropped view, each also mirrored. It costs
        four forward passes but measurably beats a single view on field photos
        (see report/metrics.json -> strategy_table, and report/improvement_log.json).
        """
        import torch
        from PIL import ImageOps

        from model.preprocess import leaf_crop_rgb

        # honour phone EXIF rotation - a rotated leaf hurts accuracy for free
        try:
            rgb = ImageOps.exif_transpose(pil_img).convert("RGB")
        except Exception:
            rgb = pil_img.convert("RGB")

        views = [self._transform(rgb)]
        if ensemble:
            leaf = leaf_crop_rgb(rgb)
            if leaf is not rgb:
                views.append(self._transform(leaf))
        t0 = time.time()
        with torch.no_grad():
            batch = torch.stack(views)
            if tta:
                batch = torch.cat([batch, torch.flip(batch, dims=[3])], dim=0)
            batch = batch.to(self.device)
            probs = torch.softmax(self.model(batch), dim=1).mean(dim=0).cpu().tolist()
        ms = round((time.time() - t0) * 1000, 1)
        order = sorted(range(len(probs)), key=lambda i: -probs[i])
        top3 = []
        for i in order[:3]:
            slug = self.classes[i]
            d = display_for(slug)
            top3.append({"class": slug, "crop": d["crop"], "condition": d["condition"],
                         "confidence": round(float(probs[i]), 4)})
        best = top3[0]
        return {
            "class": best["class"], "crop": best["crop"], "condition": best["condition"],
            "code": display_for(best["class"]).get("code"),
            "healthy": bool(display_for(best["class"]).get("healthy")),
            "confidence": best["confidence"],
            "top3": top3,
            "margin": round(top3[0]["confidence"] - (top3[1]["confidence"] if len(top3) > 1 else 0.0), 4),
            "img_size": self.img_size,
            "model_name": self.model_name,
            "inference_ms": ms,
        }

    def predict(self, image_path: str | Path, tta: bool = False) -> dict[str, Any]:
        """Predict from a file path. Raises FileNotFoundError / ValueError."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"image not found: {path}")
        if path.suffix.lower() not in IMG_EXTS:
            raise ValueError(f"unsupported image type '{path.suffix}' "
                             f"(accepted: {', '.join(sorted(IMG_EXTS))})")
        from modules.imaging import load_image
        try:
            out = self._predict_tensor(load_image(path.read_bytes()), tta=tta)
        except ValueError as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
        out.update({"source": str(path), "source_name": path.name})
        return out

    def predict_bytes(self, data: bytes, name: str = "upload.jpg",
                      tta: bool = False) -> dict[str, Any]:
        """Predict from raw bytes (HTTP upload path). Raises ValueError on bad data."""
        if not data:
            raise ValueError("empty image payload")
        # One shared loader: HEIC/HEIF, EXIF rotation, RGB normalisation, size cap.
        from modules.imaging import describe, load_image
        img = load_image(data)                      # raises ValueError with a friendly message
        out = self._predict_tensor(img, tta=tta)
        out.update({"source": None, "source_name": name, "input": describe(data, decoded=img)})
        return out

    def predict_pil(self, pil_img, tta: bool = False) -> dict[str, Any]:
        return self._predict_tensor(pil_img, tta=tta)


_SINGLETON: DiseaseClassifier | None = None


def get_classifier(reload: bool = False) -> DiseaseClassifier:
    """Process-wide singleton (loading a checkpoint is expensive)."""
    global _SINGLETON
    if _SINGLETON is None or reload:
        _SINGLETON = DiseaseClassifier()
    return _SINGLETON
