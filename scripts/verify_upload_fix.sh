#!/usr/bin/env bash
# Verification for the PC-upload fix. Run from the repo root.
set -uo pipefail
BASE=http://127.0.0.1:8000
cp samples/right/potato_early_blight__early-blight-2.jpg /tmp/pc_leaf.jpg 2>/dev/null \
  || cp "$(ls samples/right/*.jpg | head -1)" /tmp/pc_leaf.jpg

echo "=== 1. what the browser now sends for a PC upload (image + fields, NO sample_id) ==="
curl -s -X POST "$BASE/api/analyze" \
  -F "image=@/tmp/pc_leaf.jpg;type=image/jpeg" \
  -F "language=en" -F "soil_moisture_pct=24" -F "soil_ph=6.5" -F "city=Ahmedabad" \
  -F "planted_crop=tomato" -F "area_ha=1.2" -F "nitrogen=50.55" -F "phosphorus=53.36" \
  -F "potassium=48.15" -F "temperature=25.62" -F "humidity=71.48" -F "rainfall=103.46" \
  -F "use_sensors=true" > /tmp/r1.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/r1.json'))
if not d.get('prediction'):
    print('  FAILED ->', json.dumps(d)[:300]); raise SystemExit(1)
p = d['prediction']
print('  prediction :', p['condition'], f"{p['confidence']:.0%}")
print('  file used  :', p['source_name'])
print('  sample_id  :', p.get('sample_id', 'absent  <- correct'))
print('  risk       :', d['risk']['risk_label'], '| irrigation:', d['irrigation']['action'],
      '| ASI:', d['sustainability']['total'])
print('  crop rec   :', [r['crop'] for r in (d['crop_recommendation'] or {}).get('recommendations', [])])
PY

echo
echo "=== 2. regression: the old broken request shape (junk sample_id + real file) ==="
curl -s -X POST "$BASE/api/analyze" -F "image=@/tmp/pc_leaf.jpg;type=image/jpeg" \
  -F "sample_id=[object Object]" -F "soil_moisture_pct=24" > /tmp/r2.json
python3 -c "
import json; d=json.load(open('/tmp/r2.json'))
print('  ->', 'OK: uploaded file used, junk sample_id ignored' if d.get('prediction') else d)"

echo
echo "=== 3. a fake image (PDF renamed .jpg) still fails gracefully ==="
printf 'definitely not an image' > /tmp/fake.jpg
curl -s -X POST "$BASE/api/analyze" -F "image=@/tmp/fake.jpg;type=image/jpeg" > /tmp/r3.json
python3 -c "
import json; d=json.load(open('/tmp/r3.json'))
print('  ->', d.get('error'), '|', str(d.get('message'))[:70])"

echo
echo "=== 4a. a real 24 MB phone photo is ACCEPTED (the old 10 MB cap refused it) ==="
python3 - <<'PYEOF'
import io, os
from PIL import Image
side = 3600                      # camera-scale noise so the JPEG is realistically huge
img = Image.frombytes("RGB", (side, side), os.urandom(side * side * 3))
buf = io.BytesIO(); img.save(buf, format="JPEG", quality=100)
open("/tmp/big.jpg", "wb").write(buf.getvalue())
print(f"  fixture: {len(buf.getvalue())/1048576:.1f} MB")
PYEOF
curl -s -o /tmp/r4a.json -w "  http %{http_code}  " -X POST "$BASE/api/predict" \
  -F "image=@/tmp/big.jpg;type=image/jpeg"
python3 -c "
import json; d=json.load(open('/tmp/r4a.json'))
p = d.get('prediction') or {}
i = p.get('input') or {}
print(p.get('condition'), '|', i.get('size'), '->', i.get('decoded_size'), 'downscaled:', i.get('downscaled'))"

echo
echo "=== 4b. over the limit -> friendly 413 with the numbers in it ==="
python3 - <<'PYEOF'
import io, os
from PIL import Image
for side in (3800, 4100):
    img = Image.frombytes("RGB", (side, side), os.urandom(side * side * 3))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=100)
    if len(buf.getvalue()) > 26 * 1024 * 1024:
        open("/tmp/huge.jpg", "wb").write(buf.getvalue())
        print(f"  fixture: {len(buf.getvalue())/1048576:.1f} MB")
        break
else:
    raise SystemExit("could not build an oversize fixture")
PYEOF
curl -s -o /tmp/r4b.json -w "  http %{http_code}  " -X POST "$BASE/api/predict" \
  -F "image=@/tmp/huge.jpg;type=image/jpeg"
python3 -c "
import json; d=json.load(open('/tmp/r4b.json'))
print('error=', d.get('error'), '| received', d.get('received_mb'), 'MB | limit', d.get('max_mb'), 'MB')
print('  message:', str(d.get('message'))[:95])
print('  hint   :', str(d.get('hint'))[:95])
assert d.get('error') == 'image_too_large', 'expected a 413 body'
print('  OK: 413 carrying received_mb / max_mb / hint')"

echo "=== 5. served bundle contains the fixes ==="
ASSET=$(curl -s "$BASE/" | grep -o 'assets/index-[A-Za-z0-9_-]*\.js' | head -1)
echo "  asset: $ASSET"
curl -s "$BASE/$ASSET" > /tmp/bundle.js
for needle in "Analyze this photo" "HEIC" "leaf-upload" "analyze_photo"; do
  if grep -q "$needle" /tmp/bundle.js; then echo "  OK   contains: $needle"
  else echo "  MISS missing : $needle"; fi
done
