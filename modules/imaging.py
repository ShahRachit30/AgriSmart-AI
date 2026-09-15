"""Upload image loading — one place that handles every photo a farmer can hand us.

Why this module exists (two real bug reports):
  * phone photos are often **HEIC/HEIF** (iPhone default) — Pillow cannot open them
    without the optional `pillow-heif` plugin, so uploads failed with a vague error;
  * the API used to reject a file based on its **filename suffix**, so a perfectly
    valid JPEG named `image` (no extension) or `photo.unknown` was refused before
    anyone looked at the bytes.

Policy now: the bytes decide. We sniff the container, decode, normalise to RGB
(honouring EXIF rotation) and optionally downscale. Only genuinely undecodable
data is rejected, with a message that says what to do.

Diagnostics: `capabilities()` is served at GET /api/health and /api/meta so
"can this deployment read HEIC?" is answerable without reading code.
"""
from __future__ import annotations

import io
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

HEIF_OK = False
HEIF_ERROR: str | None = None
try:  # optional dependency - the app still runs (JPEG/PNG/WebP/BMP/TIFF) without it
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_OK = True
except Exception as exc:  # pragma: no cover - depends on the environment
    HEIF_ERROR = f"{type(exc).__name__}: {exc}"

# Pillow refuses absurdly large decodes (decompression-bomb protection).
MAX_PIXELS = 60_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

# Server-side cap for the longest side before the model sees the image. The network
# receives at most 160 px, so 1024 keeps every lesion detail that matters while
# halving decode time and memory for 12-48 MP phone photos.
DEFAULT_MAX_SIDE = 1024


def capabilities() -> dict[str, Any]:
    """What this deployment can actually decode (surfaced in the API)."""
    exts = [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"]
    if HEIF_OK:
        exts += [".heic", ".heif"]
    return {
        "heif": HEIF_OK,
        "heif_error": HEIF_ERROR,
        "extensions": exts,
        "max_pixels": MAX_PIXELS,
        "max_side_applied": DEFAULT_MAX_SIDE,
    }


def sniff(data: bytes) -> str:
    """Container type from magic bytes - used for logging and clear error text."""
    if len(data) < 12:
        return "unknown"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:2] == b"BM":
        return "bmp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    brand = data[4:12]
    if brand in (b"ftypheic", b"ftypheix", b"ftyphevc", b"ftyphevx", b"ftypheim",
                 b"ftypheis", b"ftypmif1", b"ftypmsf1", b"ftypavif"):
        return "heif" if brand != b"ftypavif" else "avif"
    if data[:4] == b"GIF8":
        return "gif"
    return "unknown"


def load_image(data: bytes, max_side: int | None = DEFAULT_MAX_SIDE) -> Image.Image:
    """Decode any supported upload into an RGB Pillow image.

    Raises ValueError with a farmer-friendly message on failure (never a
    traceback): empty payload, unrecognised bytes, corrupt file, or a picture so
    large that decoding it safely is impossible.
    """
    if not data:
        raise ValueError("the uploaded file was empty")
    fmt = sniff(data)
    if fmt == "heif" and not HEIF_OK:
        raise ValueError("this looks like an iPhone HEIC/HEIF photo and HEIC support is not "
                         "installed on the server - please export it as JPEG")
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()                                   # decode now: catches truncation
            img = ImageOps.exif_transpose(im).convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError(f"the uploaded file is not a readable image (detected: {fmt})") from exc
    except Image.DecompressionBombError as exc:
        raise ValueError("the image is too large to process safely - please resize it first") from exc
    except MemoryError as exc:
        raise ValueError("ran out of memory decoding this image - try a smaller photo") from exc
    except Exception as exc:
        raise ValueError(f"could not read the image ({type(exc).__name__})") from exc

    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    return img


def describe(data: bytes, decoded: Image.Image | None = None) -> dict[str, Any]:
    """Metadata for the API response and for logs (no full decode of the payload).

    `size` is what the file on disk holds; when the caller passes the image it
    actually decoded, `decoded_size`/`downscaled` also appear - so a user (or a
    judge reading the JSON) can see that a 4000 px photo was shrunk to fit the
    network instead of guessing why the numbers differ.
    """
    info: dict[str, Any] = {"bytes": len(data), "container": sniff(data)}
    try:
        with Image.open(io.BytesIO(data)) as im:
            info.update({"format": im.format, "size": list(im.size), "mode": im.mode})
    except Exception as exc:
        info["error"] = f"{type(exc).__name__}: {exc}"
    if decoded is not None:
        info["decoded_size"] = list(decoded.size)
        info["downscaled"] = list(decoded.size) != info.get("size")
    return info
