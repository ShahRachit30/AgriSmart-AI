"""Localise the knowledge base (English KB + Hindi/Gujarati overlays).

`modules/recommendations.py` owns the canonical English KB; `kb_hi.py` and `kb_gu.py`
carry the translations. This module is the merge point, so `recommendations.py` can
ask one question - "give me this entry's symptoms in Gujarati" - and always get an
answer:

    localize_entry("tomato_late_blight", "gu")   -> translated fields, English for
                                                    anything not yet translated

Product names and doses are copied verbatim in every language (the `chemical` block
is never translated): a transliterated pesticide dose is unsafe to act on. The
`chem_note` (the advisory sentence around it) *is* translated.

`checks()` reports slugs or fields still missing a language; the test suite fails
when the list is not empty, so a new disease cannot ship half-translated.
"""
from __future__ import annotations

from typing import Any

from .kb_gu import KB_GU
from .kb_hi import KB_HI

OVERLAYS: dict[str, dict[str, dict[str, str]]] = {"hi": KB_HI, "gu": KB_GU}
FIELDS = ("symptoms", "organic", "prevention", "chem_note")


def _lines(text: str | None) -> list[str]:
    return [ln.strip() for ln in (text or "").split("\n") if ln.strip()]


def localize_entry(slug: str, lang: str | None = None) -> dict[str, Any]:
    """Translated (symptoms, organic, prevention, chemical.note) for one slug.

    Returns only the keys it has: an empty dict for English, or for a slug with no
    overlay, so the caller keeps the canonical English content.
    """
    tag = (lang or "en")[:2].lower()
    overlay = OVERLAYS.get(tag, {}).get(slug)
    if not overlay:
        return {}
    out: dict[str, Any] = {}
    if overlay.get("symptoms"):
        out["symptoms"] = _lines(overlay["symptoms"])
    if overlay.get("organic"):
        out["organic"] = _lines(overlay["organic"])
    if overlay.get("prevention"):
        out["prevention"] = _lines(overlay["prevention"])
    if overlay.get("chem_note"):
        out["chem_note"] = overlay["chem_note"].strip()
    return out


def localize_kb(kb: dict[str, dict[str, Any]], lang: str | None = None) -> dict[str, dict[str, Any]]:
    """Return a copy of a KB dict with every entry's prose in `lang`."""
    tag = (lang or "en")[:2].lower()
    if tag == "en":
        return kb
    out: dict[str, dict[str, Any]] = {}
    for slug, entry in kb.items():
        item = dict(entry)
        tr = localize_entry(slug, tag)
        if tr.get("symptoms"):
            item["symptoms"] = tr["symptoms"]
        if tr.get("organic"):
            item["organic"] = tr["organic"]
        if tr.get("prevention"):
            item["prevention"] = tr["prevention"]
        chem = entry.get("chemical")
        if isinstance(chem, dict) and tr.get("chem_note"):
            item["chemical"] = {**chem, "note": tr["chem_note"]}
        out[slug] = item
    return out


def coverage(slugs: list[str] | None = None) -> dict[str, Any]:
    """How much of the KB is translated, per language (for /api/health + tests)."""
    from .recommendations import KB
    keys = slugs or list(KB)
    out: dict[str, Any] = {}
    for lang in ("hi", "gu"):
        done = [s for s in keys if localize_entry(s, lang)]
        out[lang] = {"translated": len(done), "total": len(keys),
                     "missing": sorted(set(keys) - set(done))}
    return out


def checks() -> list[str]:
    """Missing (slug, lang) pairs and missing fields within a translated entry."""
    from .recommendations import KB
    problems: list[str] = []
    for slug in KB:
        for lang in ("hi", "gu"):
            tr = localize_entry(slug, lang)
            if not tr:
                problems.append(f"{slug}:{lang}")
                continue
            english = KB[slug]
            # only require the fields the English entry actually has
            if english.get("symptoms") and not tr.get("symptoms"):
                problems.append(f"{slug}:{lang}:symptoms")
            if english.get("organic") and not tr.get("organic"):
                problems.append(f"{slug}:{lang}:organic")
            if english.get("prevention") and not tr.get("prevention"):
                problems.append(f"{slug}:{lang}:prevention")
            if (english.get("chemical") or {}).get("note") and not tr.get("chem_note"):
                problems.append(f"{slug}:{lang}:chem_note")
    return sorted(problems)
