"""Environment loading (`.env`) for the optional LLM providers.

Why this file exists
--------------------
Keys must never be committed. The convention judges and teammates expect is a
`.env` file next to `run.sh` (git-ignored, excluded from the zip), so this module
loads it once, before any provider is queried.

* `python-dotenv` is used when installed (it comes with `uvicorn[standard]`).
* Otherwise a 20-line fallback parser handles the same KEY=VALUE syntax, so the
  app never hard-depends on the package.

Precedence is the usual one: **real environment variables win** over `.env`, so
`GROQ_API_KEY=... ./run.sh` and CI secrets behave as expected.

The file never prints or logs a key - only whether one is present.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

_LOADED = False
SOURCE = "process environment"


def _parse_fallback(text: str) -> dict[str, str]:
    """Minimal dotenv parser: KEY=VALUE, # comments, optional quotes, export prefix."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_env(path: Path | None = None, *, override: bool = False) -> dict[str, str]:
    """Load `.env` into the process environment (idempotent). Returns what it set."""
    global _LOADED, SOURCE
    target = Path(path) if path else ENV_FILE
    if _LOADED and not override:
        return {}
    applied: dict[str, str] = {}
    if not target.exists():
        _LOADED = True
        return applied

    values: dict[str, str] = {}
    try:                                                        # preferred: python-dotenv
        from dotenv import dotenv_values                      # type: ignore
        values = {k: v for k, v in dotenv_values(target).items() if v is not None}
    except Exception:                                          # noqa: BLE001 - fallback is fine
        values = _parse_fallback(target.read_text(encoding="utf-8"))

    for key, value in values.items():
        if override or not os.environ.get(key):
            os.environ[key] = value
            applied[key] = value
    _LOADED = True
    if applied:
        SOURCE = f"{target.name} (+ process environment)"
    return applied


def env_path() -> Path:
    return ENV_FILE


def key_present(*names: str) -> bool:
    """True when any of the given variables holds a non-empty value."""
    return any(bool((os.getenv(name) or "").strip()) for name in names)


def mask(value: str | None) -> str:
    """`gsk_abc…xyz` - safe to show in logs/health output, reveals nothing usable."""
    if not value:
        return ""
    v = value.strip()
    if len(v) <= 8:
        return "…"
    return f"{v[:6]}…{v[-4:]}"
