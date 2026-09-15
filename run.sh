#!/usr/bin/env bash
# AgriSmart AI - one-command launch (Linux, macOS, WSL, Git Bash on Windows).
#
#   ./run.sh                  # check the environment, install what is missing, start on :8000
#   ./run.sh --port 8010      # start on another port
#   ./run.sh --doctor         # environment report only (no install, no server)
#   ./run.sh --test           # run the test suite instead of the server
#   ./run.sh --rebuild        # rebuild the React bundle, then verify it renders and switches language
#   ./run.sh --check-ui       # render the shipped bundle headlessly (blank page, stale
#                             #   "model not trained" banner)
#   ./run.sh --check-i18n     # drive the shipped bundle: does हि/ગુ change the whole UI?
#   ./run.sh --no-install     # never touch pip (assume the environment is ready)
#
# On Windows without Git Bash, use run.bat (double-click) or:
#   powershell -ExecutionPolicy Bypass -File run.ps1
#
# The app serves the API and the pre-built React UI from one port. The built UI is
# committed under app/backend/static, so Node is NOT needed to run it - only to
# rebuild the frontend.
set -euo pipefail
cd "$(dirname "$0")"

PORT=${PORT:-8000}
NO_INSTALL=0
ORIG_ARGS=("$@")

# --------------------------------------------------------------------------- #
# find a usable Python 3 interpreter
# --------------------------------------------------------------------------- #
find_python() {
  for cand in "${PY:-}" python3 python py; do
    [ -n "$cand" ] || continue
    if command -v "$cand" >/dev/null 2>&1; then
      if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        echo "$cand"; return 0
      fi
    fi
  done
  return 1
}

VENV_PY=""
venv_python() {                       # path of the interpreter inside .venv, if it exists
  if [ -x ".venv/bin/python" ]; then echo ".venv/bin/python"
  elif [ -x ".venv/Scripts/python.exe" ]; then echo ".venv/Scripts/python.exe"
  else echo ""; fi
}

PY="$(find_python || true)"
if [ -z "$PY" ]; then
  echo "!!  No Python 3.10+ found on PATH."
  echo "    Install Python 3.10-3.12 from https://www.python.org/downloads/ and re-run."
  echo "    (Windows: tick 'Add python.exe to PATH' in the installer.)"
  exit 1
fi

deps_ok() {                            # 0 = every runtime dependency imports
  "$1" - <<'EOF' >/dev/null 2>&1
import importlib.util as u
need = ["fastapi", "uvicorn", "multipart", "torch", "torchvision", "PIL", "numpy", "sklearn", "joblib", "requests"]
raise SystemExit(0 if all(u.find_spec(m) for m in need) else 1)
EOF
}

choose_interpreter() {
  local vp; vp="$(venv_python)"
  if [ -n "$vp" ] && deps_ok "$vp"; then echo "$vp"; return; fi   # an existing venv wins
  if deps_ok "$PY"; then echo "$PY"; return; fi
  echo "NEED_INSTALL"
}

install_deps() {
  local target="$1"                       # interpreter that will own the install
  echo "==> installing Python dependencies (first run only, a few minutes)"
  "$target" -m pip install --upgrade pip >/dev/null 2>&1 || true
  # CPU-only machines: the default PyPI torch wheel pulls CUDA libraries (~2 GB).
  # The CPU wheel index keeps the download around 200 MB and works everywhere.
  echo "    torch + torchvision (CPU wheels)"
  "$target" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  echo "    the rest of requirements.txt"
  "$target" -m pip install -r requirements.txt
}

# --------------------------------------------------------------------------- #
# arguments: --port / --no-install may appear anywhere before the action
# --------------------------------------------------------------------------- #
ACTION=""
while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="${2:?usage: run.sh --port 8000}"; shift 2 ;;
    --port=*) PORT="${1#*=}"; shift ;;
    --no-install) NO_INSTALL=1; shift ;;
    *) ACTION="$1"; shift ;;
  esac
done

# --------------------------------------------------------------------------- #
# actions that do not need the server
# --------------------------------------------------------------------------- #
case "$ACTION" in
  -h|--help)
    awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 && !/^#/ {exit}' "$0"
    exit 0
    ;;
  --doctor)
    exec "$PY" scripts/doctor.py --port "$PORT"
    ;;
  --test)
    if ! deps_ok "$PY" && [ -n "$(venv_python)" ]; then PY="$(venv_python)"; fi
    exec "$PY" -m pytest tests/ -q
    ;;
  --rebuild)
    command -v npm >/dev/null 2>&1 || { echo "!!  npm not found - Node.js is only needed to rebuild the UI."; exit 1; }
    (cd app/frontend && npm install --no-audit --no-fund && npm run build)
    # A bundle that compiles can still throw while rendering (blank page) ...
    node scripts/check_ui_mount.mjs
    # ... and a UI that renders can still leave English behind on a language switch.
    node scripts/check_ui_switch.mjs
    # ... and a UI that renders can still be stuck on a stale "model not trained" read.
    node scripts/check_ui_warmup.mjs
    # ... and a refusal (non-leaf photo) can still leak a diagnosis onto the page.
    node scripts/check_ui_refusal.mjs
    node scripts/check_ui_fields.mjs
    node scripts/check_ui_analyze_payload.mjs
    # ... and the live camera can capture into nothing, or dead-end when it is blocked.
    node scripts/check_ui_capture.mjs
    exit 0
    ;;
  --check-ui)
    node scripts/check_ui_mount.mjs || exit $?
    node scripts/check_ui_warmup.mjs || exit $?
    node scripts/check_ui_refusal.mjs || exit $?
    node scripts/check_ui_fields.mjs || exit $?
    node scripts/check_ui_analyze_payload.mjs || exit $?
    exec node scripts/check_ui_capture.mjs
    ;;
  --check-i18n)
    exec node scripts/check_ui_switch.mjs
    ;;
  --no-install) : ;;          # already handled above
  --port) : ;;
  "") : ;;                     # no action: start the server
  *)
    echo "!!  unknown option: $ACTION"
    echo "    ./run.sh --help"
    exit 2
    ;;
esac

# --------------------------------------------------------------------------- #
# dependencies
# --------------------------------------------------------------------------- #
TARGET="$(choose_interpreter)"
if [ "$TARGET" = "NEED_INSTALL" ]; then
  if [ "$NO_INSTALL" = "1" ]; then
    echo "!!  dependencies are missing and --no-install was given."
    "$PY" scripts/doctor.py --port "$PORT" || true
    exit 1
  fi
  if [ -n "$(venv_python)" ]; then
    TARGET="$(venv_python)"
    echo "==> using the existing virtualenv .venv"
  elif [ -n "${VIRTUAL_ENV:-}" ]; then
    TARGET="$PY"
  else
    echo "==> creating a virtualenv in .venv (keeps your system Python clean)"
    "$PY" -m venv .venv
    TARGET="$(venv_python)"
    if [ -z "$TARGET" ]; then echo "!!  could not create .venv - falling back to $PY"; TARGET="$PY"; fi
  fi
  install_deps "$TARGET"
else
  TARGET="$TARGET"
fi

# quick environment report (never fatal unless something is truly missing)
"$TARGET" scripts/doctor.py --port "$PORT" || true

[ -f model/best_model.pth ] || echo "!!  model/best_model.pth missing - the UI will start in demo mode (no detection)."

echo
echo "==> AgriSmart AI starting on http://localhost:${PORT}   (API docs: http://localhost:${PORT}/docs)"
echo "    stop with Ctrl+C"
echo
exec "$TARGET" -m uvicorn app.backend.main:app --host 0.0.0.0 --port "$PORT"
