#!/usr/bin/env bash
# Build gitproject.zip - the GitHub-ready copy of this project.
#
# Difference from scripts/package.sh: that one ships a submission bundle; this one
# ships what must go into a git repository, and it PROVES the trained model is
# included by running a real `git init && git add` on the export and listing what
# git would track. A .gitignore that excluded model/*.pth would silently produce a
# clone that starts but cannot analyse anything - that is the failure this guards.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="$(mktemp -d)"
DEST="$STAGE/AgriSmart-AI"
ZIP="${1:-/home/user/gitproject.zip}"
cd "$ROOT"

echo "==> exporting the working tree (source only, no build noise)"
mkdir -p "$DEST"
tar -cf - \
  --exclude='./.git' \
  --exclude='./.env' \
  --exclude='./data' \
  --exclude='./node_modules' \
  --exclude='./app/frontend/node_modules' \
  --exclude='./app/frontend/dist' \
  --exclude='./app/backend/__pycache__' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='.mypy_cache' \
  --exclude='.ruff_cache' \
  --exclude='.cache' \
  --exclude='*.log' \
  --exclude='./.venv' \
  --exclude='./build' \
  --exclude='./dist' \
  . | tar -xf - -C "$DEST"

# the empty data/ placeholder keeps the documented layout without shipping datasets
mkdir -p "$DEST/data" && touch "$DEST/data/.gitkeep"

echo "==> proving the model is tracked (real git, not a guess)"
( cd "$DEST" && git init -q && git add -A )
MISSING=0
for f in model/best_model.pth model/class_names.json model/leaf_gate.joblib \
         model/crop_model.joblib model/crop_label_encoder.joblib \
         model/mobilenet_v3_small_imagenet.pth \
         app/backend/static/index.html .env.example README.md PUSH_TO_GITHUB.md; do
  if ( cd "$DEST" && git ls-files --error-unmatch "$f" >/dev/null 2>&1 ); then
    printf '  OK   %s\n' "$f"
  else
    printf '  MISS %s\n' "$f"; MISSING=1
  fi
done
BEST=$( cd "$DEST" && git cat-file -s ":model/best_model.pth" )
echo "  best_model.pth content size in git: $BEST bytes"
[ "$BEST" -gt 40000000 ] || { echo "!! the model is truncated in git - aborting"; exit 1; }

echo "==> secret leak check"
if ( cd "$DEST" && git ls-files | grep -qx '.env' ); then echo "!! .env is tracked - aborting"; exit 1; fi
if grep -rIl --exclude-dir=.git -E 'gsk_[A-Za-z0-9]{20,}' "$DEST" 2>/dev/null | head -3 | grep .; then
  echo "!! a real-looking Groq key is present - aborting"; exit 1
fi
echo "  OK   no .env, no real API key"

n_files=$( cd "$DEST" && git ls-files | wc -l )
echo "==> git would track $n_files files"

echo "==> writing $ZIP"
rm -f "$ZIP"
( cd "$STAGE" && zip -q -r -X "$ZIP" AgriSmart-AI -x 'AgriSmart-AI/.git/*' )

git_cleanup=$?
rm -rf "$STAGE"
[ $MISSING -eq 0 ] || { echo "!! required files missing from the export"; exit 1; }
ls -la "$ZIP"
echo "==> done. Contents are listed by: unzip -l $ZIP | head"
