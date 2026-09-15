#!/usr/bin/env python3
"""Re-apply the backend side of the leaf-gate + version wiring to app/backend/main.py.

Kept in the repo (and run from scripts/rebuild_after_revert.sh) because a reverted
workspace that ships a frontend expecting `not_a_leaf` refusals without the backend
half would look broken to a farmer.
"""
from pathlib import Path

GUARANTEE_HELPER = True  # insertion marker
ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "backend" / "main.py"
SCHEMAS = ROOT / "app" / "backend" / "schemas.py"
ANALYSIS = ROOT / "app" / "backend" / "analysis.py"
s = MAIN.read_text()
done = []


def patch(old: str, new: str, label: str) -> None:
    global s
    assert s.count(old) == 1, f"{label}: {s.count(old)} matches"
    s = s.replace(old, new)
    done.append(label)


if 'APP_VERSION = "1.2.0"' not in s:
    if "if gate is None:" not in s:
        patch("    try:\n        return clf.predict_bytes(data, filename)",
              "    if gate is None:\n"
              "        try:\n"
              "            gate = leaf_gate.check_bytes(data)      # never gate the same photo twice\n"
              "        except Exception:                           # a broken gate must not block\n"
              "            gate = None                             # a real diagnosis\n"
              "    try:\n        out = clf.predict_bytes(data, filename)\n"
              "        if gate and gate.get(\"available\"):\n"
              "            out[\"leaf_check\"] = {\"p_leaf\": gate.get(\"p_leaf\"), "
              "\"verdict\": gate.get(\"verdict\"),\n"
              "                                 \"threshold\": gate.get(\"threshold\")}\n"
              "        return out", "gate fallback + attach")

    patch('    data, name = await _read_image(image)\n'
          '    result = _predict_from_upload(data, name)',
          '    data, name = await _read_image(image)\n'
          '    gate = _leaf_gate_or_refuse(data, name, _lang(language))\n'
          '    result = _predict_from_upload(data, name, _lang(language), gate)',
          "predict endpoint")

    patch("            prediction = _predict_from_upload(data, name)",
          "            gate = _leaf_gate_or_refuse(data, name, lang)\n"
          "            prediction = _predict_from_upload(data, name, lang, gate)",
          "analyze upload")

    patch("        prediction = _predict_from_upload(path.read_bytes(), path.name)",
          "        _raw = path.read_bytes()\n"
          "        gate = _leaf_gate_or_refuse(_raw, path.name, lang)\n"
          "        prediction = _predict_from_upload(_raw, path.name, lang, gate)",
          "analyze sample")

    patch('        "status": "ok", "version": APP_VERSION, "build_id": BUILD_ID,',
          '        "status": "ok", "version": APP_VERSION, "build_id": BUILD_ID,\n'
          '        "leaf_gate": leaf_gate.status(),', "health gate status")

    if '"leaf_gate": leaf_gate.status(),' not in s.split('"kb_classes"')[0]:
        patch('        "kb_classes": sorted(KB.keys()),',
              '        "leaf_gate": leaf_gate.status(),\n'
              '        "kb_classes": sorted(KB.keys()),', "meta gate status")

MAIN.write_text(s)
print(f"backend wiring: {len(done)} change(s)" + (f" -> {done}" if done else " (already applied)"))


def _extra() -> None:
    """The two smaller revert casualties: the health field and the soft-verdict warning."""
    s = SCHEMAS.read_text()
    if "from modules import leaf_gate" not in s and "from modules import recommendations" in s:
        patch("from modules import recommendations",
              "from modules import leaf_gate, recommendations", "gate import")

    if "def _leaf_gate_or_refuse" not in s and "def _predict_from_upload" in s:
        old = """    uploads: dict[str, Any] = {}
    assistant: dict[str, Any] = {}"""
        assert s.count(old) == 1, "schemas anchor"
        SCHEMAS.write_text(s.replace(old, """    uploads: dict[str, Any] = {}
    assistant: dict[str, Any] = {}
    # the out-of-distribution leaf gate: available / threshold / auc / reject rates
    leaf_gate: dict[str, Any] = {}"""))
        print("schemas.py: leaf_gate declared")

    s = ANALYSIS.read_text()
    if "leaf_uncertain" not in s:
        old = "    warnings: list[str] = []"
        assert s.count(old) == 1, "analysis anchor"
        ANALYSIS.write_text(s.replace(old, """    warnings: list[str] = []
    # the gate is a safety net, not a wall: in its uncertain band the analysis still
    # runs, but the farmer is told to check the photo before acting on it
    _leaf = (prediction or {}).get("leaf_check") or {}
    if _leaf.get("verdict") == "uncertain":
        warnings.append(t("leaf_uncertain", lang))"""))
        print("analysis.py: uncertain verdict warns")


_extra()


def ensure_helper() -> None:
    """The call sites and the helper were reverted out of step once, which made every
    /api/analyze request answer `NameError: _leaf_gate_or_refuse`. Guarantee both."""
    s = MAIN.read_text()
    if "def _leaf_gate_or_refuse" in s and "gate: dict[str, Any] | None = None" in s:
        return
    helper = '''def _leaf_gate_or_refuse(data: bytes, filename: str, lang: str = "en") -> dict[str, Any]:
    """Refuse photos that are not leaves, before the classifier can be confident."""
    try:
        verdict = leaf_gate.check_bytes(data)
    except Exception:                       # a broken gate must never block a diagnosis
        return {"available": False}
    if not verdict.get("available"):
        return verdict                      # no gate on disk: classify as before
    if verdict.get("verdict") == "not_leaf":
        raise HTTPException(status_code=422, detail={
            "ok": False, "error": "not_a_leaf",
            "message": t("not_a_leaf", lang),
            "hint": t("not_a_leaf_hint", lang),
            "leaf": {"p_leaf": verdict.get("p_leaf"), "verdict": verdict.get("verdict"),
                     "threshold": verdict.get("threshold")},
            "file": filename,
        })
    return verdict

'''
    old = "def _predict_from_upload(data: bytes, filename: str) -> dict[str, Any]:"
    new = (helper + "def _predict_from_upload(data: bytes, filename: str, lang: str = \"en\",\n"
           "                         gate: dict[str, Any] | None = None) -> dict[str, Any]:")
    if old in s:
        s = s.replace(old, new)
    elif "def _predict_from_upload(data: bytes, filename: str, lang" in s and "def _leaf_gate_or_refuse" not in s:
        s = s.replace("def _predict_from_upload(data: bytes, filename: str, lang",
                      helper + "def _predict_from_upload(data: bytes, filename: str, lang")
    MAIN.write_text(s)
    print("apply_backend_gate: helper + signature guaranteed")


ensure_helper()
