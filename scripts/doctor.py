#!/usr/bin/env python3
"""Environment self-check: "why does it not start on my machine?"

Run this *before* `./run.sh` when something looks wrong - it checks everything the
app needs and prints one line per item with a fix, so a judge (or a teammate on a
different laptop) can see exactly what is missing instead of reading a traceback.

    python scripts/doctor.py
    python scripts/doctor.py --port 8000     # also test whether the port is free

Exit code 0 = everything the app needs is present, 1 = at least one blocking problem.
Warnings (for example a missing optional HEIC reader) never fail the exit code.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
if os.name == "nt" and not os.environ.get("WT_SESSION"):
    GREEN = RED = YELLOW = DIM = RESET = ""          # old Windows consoles mis-render ANSI

problems: list[str] = []
warnings: list[str] = []


def line(kind: str, title: str, detail: str = "", fix: str = "") -> None:
    icon = {"ok": f"{GREEN}OK  {RESET}", "warn": f"{YELLOW}WARN{RESET}", "fail": f"{RED}FAIL{RESET}"}[kind]
    print(f"  [{icon}] {title:<44} {detail}")
    if fix and kind != "ok":
        print(f"         {DIM}-> {fix}{RESET}")


# --------------------------------------------------------------------------- #
# Python + packages
# --------------------------------------------------------------------------- #
def check_python() -> None:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 10)
    line("ok" if ok else "fail", "Python version", f"{v.major}.{v.minor}.{v.micro} ({sys.executable})",
         "install Python 3.10 or newer (3.11/3.12 recommended) - https://www.python.org/downloads/")
    if not ok:
        problems.append("python")
    if v >= (3, 13):
        line("warn", "Python 3.13 detected",
             "torch/torchvision wheels exist for 3.13, but 3.11/3.12 is the better-tested path",
             "optional: use a 3.11/3.12 virtualenv if you hit a wheel problem")


CORE = [("fastapi", "the web API"), ("uvicorn", "the server"), ("pydantic", "request models"),
        ("multipart", "photo uploads (python-multipart)"), ("torch", "the disease model"),
        ("torchvision", "image transforms"), ("PIL", "image decoding (pillow)"),
        ("numpy", "numerics"), ("sklearn", "crop recommendation (scikit-learn)"),
        ("joblib", "model loading"), ("requests", "weather + dataset download")]
OPTIONAL = [("pillow_heif", "iPhone HEIC photos", "pip install pillow-heif"),
            ("pyarrow", "the PlantVillage parquet shards (training only)", "pip install pyarrow"),
            ("matplotlib", "report plots", "pip install matplotlib"),
            ("reportlab", "the PDF report", "pip install reportlab"),
            ("pandas", "the crop dataset (training only)", "pip install pandas"),
            ("pytest", "the test suite", "pip install pytest"),
            ("httpx", "the API tests (TestClient)", "pip install httpx")]


def check_packages() -> None:
    missing_core = [n for n, _ in CORE if importlib.util.find_spec(n) is None]
    if missing_core:
        line("fail", "Required packages", f"missing: {', '.join(missing_core)}",
             "pip install -r requirements.txt   (CPU-only: install torch first - see README)")
        problems.append("packages")
    else:
        import torch
        line("ok", "Required packages", f"all {len(CORE)} present (torch {torch.__version__})")

    missing_opt = [n for n, _, _ in OPTIONAL if importlib.util.find_spec(n) is None]
    if missing_opt:
        warnings.append("optional-packages")
        line("warn", "Optional packages", f"missing: {', '.join(missing_opt)}",
             "the app still runs; install them for the full feature set / test suite")


# --------------------------------------------------------------------------- #
# Project files
# --------------------------------------------------------------------------- #
def check_files() -> None:
    weights = ROOT / "model" / "best_model.pth"
    if weights.exists():
        line("ok", "Trained weights", f"model/best_model.pth ({weights.stat().st_size / 1e6:.1f} MB)")
    else:
        line("fail", "Trained weights", "model/best_model.pth is missing",
             "the app still starts in demo mode, but detection is disabled - "
             "retrain with model/train.py or restore the file from the repo")
        problems.append("weights")

    static = ROOT / "app" / "backend" / "static"
    index, build = static / "index.html", static / "BUILD_ID.txt"
    bundles = sorted((static / "assets").glob("index-*.js")) if (static / "assets").is_dir() else []
    if index.exists() and bundles and build.exists():
        line("ok", "Built web UI", f"{bundles[0].name} (build {build.read_text().strip()})")
    else:
        line("fail", "Built web UI", "app/backend/static is missing or empty",
             "the repo ships the built UI; if it is missing: "
             "cd app/frontend && npm install && npm run build")
        problems.append("static")

    manifest = ROOT / "samples" / "manifest.json"
    if manifest.exists():
        try:
            n = len(json.loads(manifest.read_text()))
            line("ok", "Bundled demo photos", f"{n} verified samples (samples/manifest.json)")
        except Exception as exc:                                    # noqa: BLE001
            line("warn", "Bundled demo photos", f"manifest unreadable: {exc}")
    else:
        line("warn", "Bundled demo photos", "samples/manifest.json missing",
             "regenerate with scripts/curate_samples.py (needs the PlantDoc download)")

    report = ROOT / "report" / "metrics.json"
    line("ok" if report.exists() else "warn", "Metrics report",
         f"report/metrics.json ({'present' if report.exists() else 'missing'})")

    data = ROOT / "data" / "splits"
    if (data / "test_field").is_dir():
        line("ok", "Field-test split", "data/splits/test_field present")
    else:
        line("warn", "Field-test split", "data/splits is not populated",
             "only needed to retrain/evaluate - scripts/download_datasets.py + prepare_data.py. "
             "The app, the samples and the committed report do not need it.")


# --------------------------------------------------------------------------- #
# Runtime
# --------------------------------------------------------------------------- #
def check_port(port: int) -> None:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            line("ok", f"Port {port} available", "free for the server")
        except OSError:
            in_use_by_us = False
            try:
                import requests
                r = requests.get(f"http://127.0.0.1:{port}/api/health", timeout=2)
                in_use_by_us = r.ok and "model_available" in r.text
            except Exception:                                       # noqa: BLE001
                pass
            if in_use_by_us:
                line("ok", f"Port {port} already serving AgriSmart",
                     "the app is running - open http://localhost:%d" % port)
            else:
                line("fail", f"Port {port} busy", "something else is listening",
                     f"start on another port:  ./run.sh --port 8001   (or kill the other process)")
                problems.append("port")


def check_writable() -> None:
    try:
        probe = ROOT / ".doctor.tmp"
        probe.write_text("ok")
        probe.unlink()
        line("ok", "Folder writable", str(ROOT))
    except OSError as exc:
        line("fail", "Folder writable", f"cannot write to {ROOT}: {exc}",
             "unzip/clone the project into your home folder, not into a read-only location")
        problems.append("write")


def main() -> int:
    ap = argparse.ArgumentParser(description="AgriSmart AI environment check")
    ap.add_argument("--port", type=int, default=8000, help="port the server will use")
    a = ap.parse_args()

    print("\nAgriSmart AI - environment check")
    print(f"project: {ROOT}\n")
    print("Python + packages")
    check_python()
    check_packages()
    print("\nProject files")
    check_files()
    print("\nRuntime")
    check_port(a.port)
    check_writable()

    print()
    if problems:
        print(f"{RED}==> {len(problems)} blocking problem(s): {', '.join(problems)}{RESET}")
        print("    Fix the FAIL lines above, then run:  ./run.sh")
        print("    (Windows:  powershell -ExecutionPolicy Bypass -File run.ps1)")
        return 1
    if warnings:
        print(f"{YELLOW}==> ready to run, {len(warnings)} warning(s) - the app works, some extras are off.{RESET}")
    else:
        print(f"{GREEN}==> everything present. Start it with ./run.sh{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
