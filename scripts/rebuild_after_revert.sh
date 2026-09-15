#!/usr/bin/env bash
# Rebuild the whole shippable state after a workspace revert, in one command.
#
#   bash scripts/rebuild_after_revert.sh
#
# The sandbox this was developed in restores an older snapshot without warning
# (twice mid-task), which silently reverted the frontend to the pre-farmer-pass
# version, dropped the backend leaf-gate wiring, and swapped the deployed checkpoint
# back to the pre-field-adaptation one. Everything below is idempotent, so running it
# on an already-good tree is a no-op plus a verification pass.
set -uo pipefail
cd "$(dirname "$0")/.."
export TMPDIR=/var/tmp

say() { printf '\n== %s\n' "$*"; }

say "1/7 python deps"
python3 -c "import fastapi, uvicorn, torch, torchvision, PIL, numpy, sklearn" 2>/dev/null || {
  pip install -q --no-input -r requirements.txt
  pip install -q --no-input torch torchvision --index-url https://download.pytorch.org/whl/cpu
}
python3 -c "import fastapi, torch; print('   deps OK')"

say "2/7 deployed checkpoint (field-adapted v2 beats the pre-adaptation v1)"
if [ -f /home/user/backup_best_model_field_v2.pth ]; then
  python3 - <<'PY'
import shutil, torch
from pathlib import Path
backup = Path("/home/user/backup_best_model_field_v2.pth")
deployed = Path("model/best_model.pth")
if backup.exists():
    a = torch.load(backup, map_location="cpu", weights_only=False)
    try:
        b = torch.load(deployed, map_location="cpu", weights_only=False)
        same = a.get("val_macro_f1") == b.get("val_macro_f1") and len(a["classes"]) == len(b["classes"])
    except Exception:
        same = False
    if not same:
        shutil.copy2(backup, deployed)
        shutil.copy2(backup, Path("model/best_model_field.pth"))
        print("   restored the field-adapted checkpoint (v2)")
    else:
        print("   deployed checkpoint already matches the field-adapted one")
PY
else
  echo "   no backup found - leaving model/best_model.pth as it is"
fi

say "3/7 served class list matches the checkpoint"
python3 - <<'PY'
import json, torch
from pathlib import Path
ck = torch.load("model/best_model.pth", map_location="cpu", weights_only=False)
classes = list(ck["classes"])
Path("model/class_names.json").write_text(json.dumps({"order": classes}, indent=2) + "\n")
print(f"   class_names.json -> {len(classes)} classes ({ck.get('model_name')}, {ck.get('img_size')}px)")
PY

say "4/7 farmer UI + backend leaf gate"
python3 scripts/apply_farmer_pass.py
python3 scripts/apply_farmer_results_i18n_css.py
python3 scripts/apply_backend_gate.py
python3 scripts/apply_analyze_fix.py   # optional-field sanitiser + client unwrap + tests

say "5/7 frontend build"
cd app/frontend
[ -d node_modules ] || npm install --silent
npm run build 2>&1 | tail -2
cd ../..
cat app/backend/static/BUILD_ID.txt

say "6/7 tests + UI checks"
python3 -m pytest -q tests/ 2>&1 | tail -3
for c in mount switch warmup refusal capture; do
  printf '%-8s ' "$c"
  node "scripts/check_ui_$c.mjs" 2>&1 | tail -1
done

say "7/7 handover zip"
bash scripts/package.sh --check 2>&1 | tail -5 || bash scripts/package.sh 2>&1 | tail -5

say "done"
