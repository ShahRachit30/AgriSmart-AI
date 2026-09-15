"""Field-photo preprocessing helpers.

`leaf_crop()` finds the dominant leaf in a cluttered field photo and crops to it.
Motivation (measured, see report/metrics.json `strategy_table`): the classifier is
trained on PlantVillage, where the leaf fills the frame. Real photos are mostly
background - soil, hands, sky - so feeding the whole frame dilutes the signal.
Locating the green region and cropping tight recovers part of that framing.

Algorithm (no heavy dependencies - PIL + numpy + scipy.ndimage, all pulled in by
scikit-learn/tochvision already):

1. downscale to 256 px on the long side (speed),
2. build a green mask in HSV (leaf hues, with saturation/value floors),
3. clean it with a binary opening followed by a closing (removes noise, fills gaps),
4. label connected components and keep the largest blob,
5. crop the original image to that blob's bounding box, padded by `pad`,
6. fall back to the untouched image when no plausible leaf is found.

This is deliberately conservative: a wrong crop is worse than no crop, so the
fallback triggers on tiny/oversized/edge-hugging regions.
"""
from __future__ import annotations

from typing import Any

from PIL import Image

# PIL HSV scale is 0-255 for hue. Healthy leaf green sits roughly at 55-115.
HUE_LO, HUE_HI = 45, 125
SAT_MIN = 45
VAL_MIN = 35
MIN_AREA_FRAC = 0.03     # ignore specks (3 % of the frame)
MAX_AREA_FRAC = 0.985    # a blob covering ~everything is not a useful crop
DOWNSCALE = 256


def leaf_bbox(img: Image.Image, pad: float = 0.08) -> tuple[int, int, int, int] | None:
    """Bounding box of the largest leaf-like (green) region, or None."""
    import numpy as np
    from scipy import ndimage

    small = img.convert("RGB")
    w, h = small.size
    scale = DOWNSCALE / max(w, h)
    if scale < 1:
        small = small.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
    arr = np.asarray(small).astype(np.int16)
    hsv = np.asarray(small.convert("HSV")).astype(np.int16)

    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    mask = (hue >= HUE_LO) & (hue <= HUE_HI) & (sat >= SAT_MIN) & (val >= VAL_MIN)
    # also accept dark-green pixels where hue is unreliable (shadowed leaves)
    g, r, b = arr[..., 1], arr[..., 0], arr[..., 2]
    mask |= (g > r + 12) & (g > b + 12) & (g > 35)

    struct = np.ones((3, 3), bool)
    mask = ndimage.binary_opening(mask, structure=struct)
    mask = ndimage.binary_closing(mask, structure=struct)

    labels, n = ndimage.label(mask)
    if n == 0:
        return None
    sizes = ndimage.sum(mask, labels, range(1, n + 1))
    biggest = int(np.argmax(sizes)) + 1
    area_frac = float(sizes[biggest - 1]) / float(mask.size)
    if not (MIN_AREA_FRAC <= area_frac <= MAX_AREA_FRAC):
        return None
    ys, xs = np.where(labels == biggest)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1

    # scale the box back to the original resolution and pad it
    sw, sh = small.size
    fx, fy = w / sw, h / sh
    bw, bh = (x1 - x0) * fx, (y1 - y0) * fy
    px, py = bw * pad, bh * pad
    x0, y0 = max(0.0, x0 * fx - px), max(0.0, y0 * fy - py)
    x1, y1 = min(float(w), x1 * fx + px), min(float(h), y1 * fy + py)
    box = (int(x0), int(y0), int(x1), int(y1))
    if box[2] - box[0] < 16 or box[3] - box[1] < 16:
        return None
    return box


def leaf_crop(img: Image.Image, pad: float = 0.08) -> Image.Image:
    """Crop to the dominant leaf when one can be found confidently."""
    box = leaf_bbox(img, pad)
    return img.crop(box) if box else img


def leaf_crop_rgb(img: Image.Image, pad: float = 0.08) -> Image.Image:
    return leaf_crop(img.convert("RGB"), pad)


def diagnose(img: Image.Image) -> dict[str, Any]:
    """Small introspection helper used by tests and the CLI."""
    box = leaf_bbox(img)
    w, h = img.size
    if box is None:
        return {"found": False, "image_size": [w, h]}
    return {
        "found": True, "box": list(box), "image_size": [w, h],
        "area_fraction": round(((box[2] - box[0]) * (box[3] - box[1])) / float(w * h), 3),
    }
