"""AgriSmart AI domain modules (pure-Python decision support).

Import cost is kept low on purpose: heavy deps (torch, sklearn) live in `model/`
and `scripts/`, so `import modules` stays instant for the API and the tests.

* i18n               - EN/HI/GU strings + fallback reporting
* weather            - Open-Meteo client + published irrigation thresholds
* recommendations    - 18-class knowledge base + risk engine
* sustainability     - AgriSmart Sustainability Index (published formula)
* assistant          - grounded Q&A (+ optional LLM), provenance in every answer
* crop_recommendation- Bonus A RandomForest (envelope fallback)
* iot_sim            - Bonus F simulated ESP32 feed + firmware contract
"""
from __future__ import annotations

__all__ = ["i18n", "weather", "recommendations", "sustainability", "assistant",
           "crop_recommendation", "iot_sim"]
__version__ = "1.1.0"
