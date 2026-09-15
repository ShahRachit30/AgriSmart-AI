#!/usr/bin/env python3
"""One-command end-to-end demo (no server needed) - handy for judges and CI.

    python scripts/demo.py                      # uses a random field photo
    python scripts/demo.py --image leaf.jpg     # or your own photo
    python scripts/demo.py --lang hi            # answers in Hindi

Walks the same code path as the API: classifier -> risk -> irrigation ->
sustainability -> crop recommendation -> grounded assistant, then prints a
readable summary and the JSON payload keys.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.analysis import run_analysis  # noqa: E402
from model.inference import get_classifier  # noqa: E402
from modules import assistant as assistant_mod  # noqa: E402

BAR = "─" * 78


def pick_image() -> Path | None:
    field = ROOT / "data" / "splits" / "test_field"
    if not field.is_dir():
        return None
    imgs = [p for p in field.rglob("*.jpg")]
    return random.choice(imgs) if imgs else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", default=None)
    ap.add_argument("--city", default="Ahmedabad")
    ap.add_argument("--soil", type=float, default=24.0)
    ap.add_argument("--lang", default="en", choices=("en", "hi", "gu"))
    ap.add_argument("--question", default="What should I do about this?")
    a = ap.parse_args()

    image = Path(a.image) if a.image else pick_image()
    print(BAR)
    print("AgriSmart AI - end-to-end demo")
    print(BAR)

    prediction = None
    clf = get_classifier()
    if image and clf.available:
        try:
            prediction = clf.predict(image)
            print(f"image        : {image}")
            print(f"prediction   : {prediction['class']} "
                  f"({prediction['condition']}, {prediction['confidence']:.1%})")
        except Exception as exc:
            print(f"prediction   : skipped ({exc})")
    elif image and not clf.available:
        print(f"image        : {image}")
        print(f"prediction   : model unavailable - {clf.load_error}")

    analysis = run_analysis(
        prediction=prediction, soil_moisture_pct=a.soil, soil_ph=6.5, city=a.city,
        planted_crop="tomato", area_ha=1.2,
        crop_inputs={"N": 90, "P": 42, "K": 43, "temperature": 24, "humidity": 80,
                     "ph": 6.5, "rainfall": 200},
        language=a.lang,
    )

    irr = analysis["irrigation"]
    print(f"irrigation   : {irr['action']} - {irr['action_label']}")
    print(f"               {irr['reasons'][0]}")
    wx = analysis["weather"] or {}
    print(f"weather      : {'live' if wx.get('ok') else 'offline'} "
          f"{wx.get('temperature_c', '')}C {wx.get('condition', '')} "
          f"rain {wx.get('rain_probability_pct', '')}%")
    if analysis["risk"]:
        r = analysis["risk"]
        print(f"risk         : {r['risk_label']} ({r['advisory_level']}) - {r['condition']}")
    s = analysis["sustainability"]
    print(f"sustainability: {s['total']}/100 grade {s['grade']} ({s['band']}), "
          f"weakest {s['weakest_area']}")
    if analysis["crop_recommendation"]:
        cr = analysis["crop_recommendation"]
        print("crop advice  : " + ", ".join(
            f"{r['crop']} {r['probability']:.0%}" for r in cr["recommendations"]))
    print(f"sensors      : simulated node {analysis['sensors']['device_id']} "
          f"soil {analysis['sensors']['soil_moisture_pct']}%")

    ctx = {k: analysis[k] for k in ("prediction", "risk", "irrigation", "weather",
                                    "sustainability", "crop_recommendation", "sensors")}
    answer = assistant_mod.answer(a.question, ctx, a.lang)
    print(BAR)
    print(f"Q ({answer['language']}): {a.question}")
    print(f"A: {answer['answer']}")
    print(f"   engine={answer['engine']} intent={answer['intent']} "
          f"sources={len(answer['sources'])}")
    print(BAR)
    print("payload keys:", ", ".join(sorted(analysis.keys())))
    print(f"\nanalysis JSON size: {len(json.dumps(analysis)) / 1024:.1f} kB "
          f"(session {analysis['session_id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
