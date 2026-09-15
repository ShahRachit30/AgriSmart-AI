#!/usr/bin/env python3
"""PS section 4.1 interface: a single-image disease prediction entry point.

Usage
-----
    python predict.py --image path/to/leaf.jpg            # prints the class label
    python predict.py --image leaf.jpg --json             # label + confidence + top-3
    python predict.py --image leaf.jpg --top 5 --json
    python predict.py --image leaf.jpg --advisory         # + risk card & actions

Python
------
    from predict import predict
    result = predict("leaf.jpg")          # -> dict, see model/inference.py

The CLI exits 0 on success and 2 on a clean error message (never a traceback),
so it can be called from scripts or a judge's shell safely.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from model.inference import DiseaseClassifier, get_classifier  # noqa: E402
from modules.i18n import t  # noqa: E402
from modules.recommendations import actions_for, assess_risk  # noqa: E402


def predict(image_path: str | Path, classifier: DiseaseClassifier | None = None,
            gate: bool = True) -> dict:
    """Predict the disease class for one image. Raises FileNotFoundError/ValueError.

    With `gate=True` (default) a photo that the leaf gate scores as "not a leaf"
    raises NotALeafError instead of returning a confident disease label - the same
    refusal the API gives. `--no-gate` on the CLI turns it off for batch jobs.
    """
    clf = classifier or get_classifier()
    if not clf.available:
        raise RuntimeError(clf.load_error or "disease model unavailable")
    if gate:
        check = _gate_for_path(image_path)
        if check.get("verdict") == "not_leaf":
            raise NotALeafError(image_path, check)
    return clf.predict(image_path)


class NotALeafError(ValueError):
    """Raised when the leaf gate refuses the photo (out-of-distribution input)."""

    def __init__(self, path: str | Path, check: dict):
        self.path, self.check = str(path), check
        super().__init__(f"{path}: not a leaf photo (leaf confidence "
                         f"{check.get('p_leaf')}, threshold {check.get('threshold')})")


def _gate_for_path(image_path) -> dict:
    try:
        from modules import leaf_gate
        from PIL import Image
        if not leaf_gate.available():
            return {"available": False, "verdict": "unknown", "p_leaf": None}
        with Image.open(image_path) as img:
            img.load()
            return leaf_gate.check_pil(img)
    except FileNotFoundError:
        raise
    except Exception as exc:                                    # never block a prediction on the gate
        return {"available": False, "verdict": "unknown", "p_leaf": None,
                "reason": f"{type(exc).__name__}: {exc}"}


def predict_bytes(data: bytes, name: str = "upload.jpg",
                  classifier: DiseaseClassifier | None = None) -> dict:
    """Same contract for an in-memory image (used by the FastAPI layer)."""
    clf = classifier or get_classifier()
    if not clf.available:
        raise RuntimeError(clf.load_error or "disease model unavailable")
    return clf.predict_bytes(data, name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--image", required=True, help="path to a leaf photo")
    ap.add_argument("--json", action="store_true", help="full JSON result")
    ap.add_argument("--top", type=int, default=3, help="how many classes to list (<=5)")
    ap.add_argument("--advisory", action="store_true", help="add knowledge-base risk + actions")
    ap.add_argument("--lang", default="en", help="en | hi | gu (used by --advisory)")
    ap.add_argument("--no-gate", dest="gate", action="store_false", default=True,
                    help="skip the 'is this a leaf?' gate (batch jobs only)")
    a = ap.parse_args()
    try:
        clf = get_classifier()
        if not clf.available:
            print(f"model unavailable: {clf.load_error}", file=sys.stderr)
            return 2
        res = predict(a.image, classifier=clf, gate=a.gate)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except NotALeafError as exc:
        print(f"not a leaf: {exc}", file=sys.stderr)
        print("  the gate refused this photo - it is not a leaf, so no diagnosis is "
              "reported (use --no-gate to force one)", file=sys.stderr)
        return 3
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    top = res["top3"][: max(1, min(a.top, 5))]
    if a.advisory:
        risk = assess_risk(res["class"], res["confidence"], None, a.lang)
        res["risk"] = risk
        res["actions"] = actions_for(res["class"], risk["risk"], a.lang)
        res["disclaimer"] = t("disclaimer", a.lang)

    if a.json:
        print(json.dumps({**res, "top3": top}, indent=2, ensure_ascii=False))
    else:
        print(f"{res['class']}")
        print(f"  crop      : {res['crop']}")
        print(f"  condition : {res['condition']}")
        print(f"  confidence: {res['confidence']:.1%}")
        print(f"  top-{len(top)}     : " +
              ", ".join(f"{r['class']} {r['confidence']:.1%}" for r in top))
        print(f"  model     : {res['model_name']} @{res['img_size']}px ({res['inference_ms']} ms)")
        if a.advisory:
            print(f"  risk      : {res['risk']['risk_label']} ({res['risk']['advisory_level']})")
            for act in res["actions"][:3]:
                print(f"    [{act['priority']}] {act['text']}")
            print(f"  {res['disclaimer']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
