#!/usr/bin/env bash
# Full recovery + GitHub-ready export, in one shot.
#
# The sandbox reverts the workspace to the 2026-09-12 snapshot every few turns
# (reverts #5..#8 so far: farmer UI gone, backend back to 1.1.2, model swapped to the
# pre-adaptation v1, node_modules and test fixtures wiped). This script puts it all
# back and then builds both zips, so the whole recovery is one command.
#
#   bash scripts/recover_all.sh
#
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$PWD"
export TMPDIR=/var/tmp

step() { printf '\n== %s\n' "$1"; }

step "1/7 trained model (the deployed file must be the field-adapted v2)"
if [ -f /home/user/backup_best_model_field_v2.pth ]; then
  python3 - <<'PY'
import hashlib, shutil
from pathlib import Path
src, dst = Path("/home/user/backup_best_model_field_v2.pth"), Path("model/best_model.pth")
v1 = Path("/home/user/backup_best_model_v1.pth")
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
if not dst.exists() or h(dst) == h(v1):
    shutil.copy2(src, dst)
    shutil.copy2(src, Path("model/best_model_field.pth"))
    print("   restored the field-adapted v2 checkpoint (was the v1 trap)")
else:
    print("   deployed checkpoint matches v2 - untouched")
print("   model sha256:", h(Path("model/best_model.pth"))[:16])
PY
else
  echo "   !! /home/user/backup_best_model_field_v2.pth missing - cannot verify the model"
fi

step "2/7 dataset symlink + non-leaf test fixtures"
[ -d /var/tmp/agrismart-data ] || mkdir -p /var/tmp/agrismart-data/{raw,tmp}
[ -e data ] || ln -s /var/tmp/agrismart-data data
python3 scripts/make_non_leaf_fixtures.py 2>&1 | tail -3

step "3/7 farmer UI + backend gate + analyse fixes (idempotent)"
python3 scripts/apply_farmer_pass.py 2>&1 | tail -2
python3 scripts/apply_farmer_results_i18n_css.py 2>&1 | tail -2
python3 scripts/apply_backend_gate.py 2>&1 | tail -2
python3 scripts/apply_analyze_fix.py 2>&1 | tail -2

step "4/7 frontend dependencies + build"
cd app/frontend
[ -d node_modules ] || { echo "   npm install (first time after a wipe, ~1-2 min)"; npm install --silent 2>&1 | tail -2; }
npm run build 2>&1 | tail -3
cd "$ROOT"
echo "   BUILD_ID: $(cat app/backend/static/BUILD_ID.txt)"

step "5/7 markers"
printf '   helper in main.py : %s (must be 1)\n' "$(grep -c 'def _leaf_gate_or_refuse' app/backend/main.py)"
printf '   gate import       : %s (must be >= 1)\n' "$(grep -c 'leaf_gate' app/backend/main.py)"
printf '   farmer UI         : %s (must be >= 1)\n' "$(grep -c 'LiveCapture' app/frontend/src/App.jsx)"
printf '   analyse sanitiser : %s\n' "$([ -f app/frontend/src/fields.mjs ] && echo present || echo MISSING)"
printf '   APP_VERSION       : %s\n' "$(grep -o 'APP_VERSION = "[0-9.]*"' app/backend/main.py)"

step "6/7 tests + UI checks (server must be stopped - 2 GB box)"
python3 -m pytest tests/ -q 2>&1 | tail -3
for c in mount switch warmup refusal capture fields analyze_payload; do
  printf '   %-16s ' "$c"
  node "scripts/check_ui_$c.mjs" >/tmp/check_$c.log 2>&1 && echo "PASS" || { echo "FAIL"; tail -4 /tmp/check_$c.log; }
done

step "7/7 zips"
bash scripts/build_gitproject.sh /home/user/gitproject.zip 2>&1 | tail -6
bash scripts/package.sh 2>&1 | tail -3

echo
echo "== recovery complete: $(cat app/backend/static/BUILD_ID.txt)"
