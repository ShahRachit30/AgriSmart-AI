#!/usr/bin/env bash
# Build the GitHub-ready zip: /home/user/AgriSmart-AI.zip
#
#   bash scripts/package.sh          # build/refresh the zip
#   bash scripts/package.sh --check  # verify the zip contents instead
#
# The zip is the submission artifact: it carries the trained weights
# (model/best_model.pth), the bundled demo samples and the *pre-built* React
# bundle (app/backend/static), so a judge can run ./run.sh without Node.
# Regenerable data (data/raw, data/splits) and caches are excluded.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
OUT="${OUT:-/home/user/AgriSmart-AI.zip}"
NAME="AgriSmart-AI"

EXCLUDES=(
  "$NAME/app/frontend/node_modules/*"
  "*__pycache__*" "*.pyc" "*.pyo"
  "$NAME/.pytest_cache/*" "$NAME/.ruff_cache/*" "$NAME/.mypy_cache/*"
  "$NAME/data/raw/*" "$NAME/data/tmp/*" "$NAME/data/splits/*" "$NAME/data/splits_field/*" \
  "$NAME/data/report/*" "$NAME/data/negatives/*" \
  "$NAME/model/_finetune_state.pt" "$NAME/model/_finetune_state.tmp" \
  "$NAME/model/best_model_field.pth"   # stage-2 output; it is copied to best_model.pth
  "$NAME/report/train_stdout.log" "*.log"
  "$NAME/.git/*" "$NAME/.venv/*" "$NAME/app/frontend/dist/*"
  "$NAME/.env" "$NAME/.env.local" "$NAME/.env.production"   # secrets never ship
  "*.DS_Store"
)

if [ "${1:-}" = "--check" ]; then
  echo "==> inspecting $OUT"
  # Listing once matters: `unzip | grep -q` under `set -o pipefail` reports a
  # false MISS, because grep exits on the first hit and SIGPIPEs unzip.
  LIST="$(mktemp)"
  unzip -l "$OUT" > "$LIST"
  printf '  %s files, %s
' "$(grep -c 'AgriSmart-AI/' "$LIST" || true)" "$(ls -lh "$OUT" | awk '{print $5}')"
  echo "--- must contain ---"
  for needle in model/best_model.pth app/backend/static/BUILD_ID.txt \
                app/backend/static/index.html samples/manifest.json \
                modules/imaging.py scripts/verify_upload_fix.sh \
                app/frontend/src/App.jsx tests/test_imaging.py requirements.txt \
                README.md .gitignore .gitattributes run.sh run.bat run.ps1 \
                scripts/doctor.py scripts/check_ui_switch.mjs scripts/check_ui_warmup.mjs \
                scripts/check_ui_refusal.mjs scripts/check_ui_fields.mjs \
                scripts/check_ui_analyze_payload.mjs scripts/check_ui_capture.mjs tests/test_ui_language.py \
                model/leaf_gate.joblib model/mobilenet_v3_small_imagenet.pth \
                scripts/train_leaf_gate.py scripts/finetune_field.py scripts/build_field_split.py \
                tests/test_leaf_gate.py tests/fixtures/non_leaf/office_chair.jpg \
                docs/ui/dashboard.png docs/ui/results.png; do
    if grep -qF -- "$needle" "$LIST"; then echo "  OK   $needle"
    else echo "  MISS $needle"; fi
  done
  echo "--- must NOT contain ---"
  for banned in node_modules __pycache__ data/raw data/splits data/tmp .venv data/splits_field \
                _finetune_state; do
    if grep -qF -- "$banned" "$LIST"; then echo "  LEAK $banned"
    else echo "  OK   no $banned"; fi
  done
  # the served bundle must be the one BUILD_ID.txt claims
  echo "--- build stamp ---"
  BID="$(unzip -p "$OUT" AgriSmart-AI/app/backend/static/BUILD_ID.txt)"
  echo "  BUILD_ID.txt : $BID"
  grep -o 'assets/index-[A-Za-z0-9_-]*\.js' "$LIST" | sort -u | sed 's/^/  bundle       : /'
  rm -f "$LIST"
  exit 0
fi

echo "==> packaging $ROOT -> $OUT"
rm -f "$OUT"
( cd "$(dirname "$ROOT")" && zip -q -X -r "$OUT" "$NAME" \
    -x "${EXCLUDES[@]}" )
ls -lh "$OUT"
echo "==> done. Verify with: bash scripts/package.sh --check"


# --- prune empty data placeholders -------------------------------------------
# `data/` is a symlink to a scratch disk in this sandbox, so the archive can pick up
# empty data/splits* directory entries. They are noise in a handover zip - drop them.
python3 - <<'PYEOF'
import zipfile, sys
from pathlib import Path
zip_path = Path(__file__).resolve().parents[1].parent / "AgriSmart-AI.zip"
if zip_path.exists():
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        empty = [n for n in names if n.startswith("AgriSmart-AI/data/")]
        keep = [n for n in names if n not in empty]
        if empty:
            import shutil, tempfile
            tmp = zip_path.with_suffix(".tmp.zip")
            with zipfile.ZipFile(zip_path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
                for item in src.infolist():
                    if item.filename in empty:
                        continue
                    dst.writestr(item, src.read(item.filename))
            tmp.replace(zip_path)
            print(f"  pruned {len(empty)} empty data/ entries from the zip")
PYEOF
