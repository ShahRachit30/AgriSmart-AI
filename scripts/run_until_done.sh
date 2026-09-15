#!/usr/bin/env bash
# Run a training command until its checkpoint appears, resuming after a kill.
#
# Why: this sandbox recycles (wipes processes) every so often. `model/train.py` writes an
# epoch-level state file under `model/_train_state.pt`, so a restart resumes at the next
# epoch instead of starting over. Without this loop a recycle mid-run means the whole
# training is lost, which is exactly what happened twice.
#
#   bash scripts/run_until_done.sh model/best_model38.pth -- python3 -u model/train.py ...
#
# Exits when the target file exists (success) or after MAX_TRIES restarts.
set -uo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:?usage: run_until_done.sh TARGET -- COMMAND...}"
shift
[ "${1:-}" = "--" ] && shift
[ "$#" -gt 0 ] || { echo "no command given" >&2; exit 2; }

MAX_TRIES="${MAX_TRIES:-6}"
for try in $(seq 1 "$MAX_TRIES"); do
  if [ -f "$TARGET" ] && python3 - "$TARGET" <<'PY'
import sys, time, os
p = sys.argv[1]
# a checkpoint younger than 1 minute may still be mid-write; treat only older ones as final
sys.exit(0 if (time.time() - os.path.getmtime(p)) > 60 else 1)
PY
  then
    echo "==> $TARGET is complete (attempt $try)"; exit 0
  fi
  echo "==> attempt $try/$MAX_TRIES: $*"
  "$@"
  code=$?
  echo "==> command exited with $code"
  [ -f "$TARGET" ] && { echo "==> $TARGET exists - done"; exit 0; }
  sleep 5
done
echo "!! gave up after $MAX_TRIES attempts" >&2
exit 1
