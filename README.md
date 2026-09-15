# 🌿 AgriSmart AI — Crop Disease Detection & Farm Decision Support

Upload a photo of a leaf → get the disease, the confidence, and what to do about it — in
**English, हिंदी or ગુજરાતી**, with weather-aware irrigation, a crop recommendation and a
grounded farmer assistant.

![dashboard](docs/ui/dashboard.png)

---

## 1. Modules built — core and bonus

| # | Module | Type | What it does | Where |
|---|---|---|---|---|
| 1 | **Crop disease detection** | **CORE** | ResNet18 transfer learning, **18 classes** across 6 crops, single-image `predict(image_path)` interface, honest lab **and field** evaluation | `model/`, `predict.py` |
| 2 | Smart irrigation | bonus | Rule engine over soil moisture + rain forecast, published thresholds | `modules/weather.py` |
| 3 | Weather intelligence | bonus | Live Open-Meteo data, WMO interpretation, 7-day outlook, ET₀ proxy; degrades gracefully offline | `modules/weather.py` |
| 4 | Sustainability score | bonus | AgriSmart Sustainability Index with a published formula | `modules/sustainability.py` |
| 5 | Farmer assistant | bonus | Grounded Q&A over the analysis context — no invented facts; optional LLM phrasing via Groq/OpenAI/Gemini from `.env` | `modules/assistant.py` |
| 6 | Multilingual UI (EN/हि/ગુ) | bonus | Every module, card and server-provided string re-localizes live | `app/frontend/src/i18n.js`, `modules/kb_i18n.py` |
| 7 | Crop recommendation | bonus | RandomForest over the public Crop-Recommendation dataset (22 crops) | `modules/crop_recommendation.py` |
| 8 | IoT integration | bonus | Documented **simulated** ESP32-style sensor stream + firmware ingest contract | `modules/iot_sim.py` |

**Stack.** React + Vite front end, served by FastAPI from `app/backend/static` — one
origin, no CORS, no second deployment. PyTorch (CPU) for inference.

---

## 2. Setup and run — reproduce a prediction in under 10 minutes

```bash
# 1) install (CPU wheels: ~200 MB instead of ~2 GB)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 2) predict a leaf (the Section 4.1 single-image interface)
python predict.py --image samples/right/grape_black_rot__000gb.jpg
```

Verified output on the bundled sample:

```
  prediction: grape_black_rot
  crop      : Grape
  condition : Black Rot
  confidence: 99.5%
  top-3     : grape_black_rot 99.5%, apple_healthy 0.1%, tomato_healthy 0.1%
  model     : resnet18 @160px (56.0 ms)
```

```bash
python predict.py --image leaf.jpg --json        # label + confidence + top-3 (machine-readable)
python predict.py --image leaf.jpg --advisory    # + knowledge-base risk and recommended actions
python predict.py --image leaf.jpg --top 5
```

From Python:

```python
from predict import predict
result = predict("samples/right/apple_scab__img_1916.jpg")
print(result["prediction"]["class"], result["prediction"]["confidence"])
```

### Run the full web app

```bash
./run.sh              # Linux / macOS / WSL / Git Bash  ->  http://localhost:8000
run.bat               # Windows (PowerShell: run.ps1, optional -Port)
```

`run.sh` finds Python, creates `.venv` if needed, installs the CPU wheels, prints an
environment report and starts the server. Node.js is **not** required to run the app.

Optional — enable the LLM phrasing for the farmer assistant:

```bash
cp .env.example .env      # then put your GROQ_API_KEY=... in .env (never commit it)
```

**Troubleshooting.** `python scripts/doctor.py` checks Python version, packages, weights,
built UI and port conflicts, with a fix per line. Everything except the live weather card
works offline, and the UI says so (`Weather: offline`) rather than failing.

---

## 3. Datasets used, source and licence

| Dataset | Used for | Source | Licence / note |
|---|---|---|---|
| **PlantVillage** (38-class photo dataset, 54,303 images) | **Core** lab training and the in-domain validation split | Kaggle `vipoooool/new-plant-diseases-dataset` ; mirrored on Hugging Face as `dpdl-benchmark/plant_village`, which is what the scripts fetch | Public research dataset (PlantVillage, Penn State); the Kaggle copy is a re-augmented version of the original |
| **PlantDoc** (field photos, real backgrounds/lighting) | **Domain adaptation + field evaluation**; its test and hold-out splits were **never trained on** | `github.com/pratikkayal/PlantDoc-Dataset` | MIT licence (see the repository); 
| **Caltech-101** | Negatives for the "is this even a leaf?" gate | `data.caltech.edu` via torchvision | Public research dataset |
| **Crop-Recommendation** (2,200 rows, 22 crops) | Bonus crop recommender | Kaggle `atharvaingle/crop-recommendation-dataset` | CC0 |

Only the **18 classes** of the shipped model are scored. Three of them have no examples in
the field splits and are reported as *absent*, never silently scored.

---

## 4. Reported metrics (every model)

Full machine-readable numbers live in `report/*.json`; the confusion matrix is
`report/confusion_matrix.png`.

### 4.1 Crop disease classifier — the core model

| Evaluation | Split | Images | Accuracy | **Macro-F1** | Top-3 |
|---|---|---|---|---|---|
| **Held-out FIELD (primary)** | PlantDoc test, never trained on | 128 | **0.5938** | **0.5782** | 0.8828 |
| Held-out FIELD (secondary, larger) | PlantDoc hold-out, never trained on | 365 | 0.5836 | **0.5966** | 0.8329 |
| In-domain LAB (reference) | PlantVillage validation | 984 | 0.9939 | **0.9944** | 1.0000 |

The lab number is high because PlantVillage is photographed on plain backgrounds. The
**field** number is the honest one: same model, real photos with soil, hands, shadows and
blur. Per-class precision/recall and the confusion matrix are in `report/model_report.md`
and `report/confusion_matrix.png`.

### 4.2 Baseline comparison

The pre-adaptation checkpoint (trained on lab photos only) was evaluated on the **same**
field split:

| Model | Field accuracy | Field macro-F1 |
|---|---|---|
| Baseline — lab-only checkpoint | 0.3047 | 0.2986 |
| **Shipped — field-adapted** | **0.5938** | **0.5782** |

That is a **+94 % relative macro-F1** improvement on real field photos, and it is why the
two-stage training (lab pre-training → field adaptation) exists.

### 4.3 Other models

| Model | Metric | Result |
|---|---|---|
| Crop recommender (RandomForest, 200 trees) | Accuracy / macro-F1 on 440 held-out rows | 0.9773 / 0.9770 |
| Leaf gate (MobileNetV3-small features + logistic regression) | ROC-AUC | 0.998 |
| Leaf gate behaviour | Non-leaf photos refused / real leaves wrongly refused | 96.9 % / 1.1 % |

---

## 5. Architecture overview and known limitations

### Architecture

```
leaf photo ─► leaf gate ──► not a leaf? ─► friendly refusal (no diagnosis)
                  │
                  └─ leaf ─► ResNet18 @160px (center-crop + mirror TTA)
                                │
                                ├─► top-1 / top-3 disease + confidence
                                ├─► knowledge base: risk, actions, prevention (EN/HI/GU)
                                ├─► weather + soil  ─► irrigation advice
                                ├─► sustainability score
                                └─► farmer assistant (grounded Q&A)
```

* **Backbone:** ResNet18, ImageNet-pretrained, 160 px input, 18-way head.
* **Stage 1 — lab pre-training:** 16 epochs, AdamW (backbone 2e-4, head 1e-3), batch 12,
  augmentation (flip, rotation, colour jitter), early stopping on validation macro-F1.
* **Stage 2 — field adaptation:** 1,782 PlantDoc field photos + 2,500 lab replay images per
  epoch, best checkpoint at epoch 8; this is the step that produces the honest field number.
* **Decoding:** center-crop + mirror TTA, chosen by measuring four decodings on the field split.
* **Gate:** MobileNetV3-small embeddings + logistic regression (AUC 0.998), so a chair or a
  screenshot is refused instead of diagnosed.

### Known limitations (honest)

1. **Lab → field gap.** Field macro-F1 is ~0.58 while lab macro-F1 is ~0.99. Real photos
   (blur, occlusion, mixed lighting) remain the hard case; the app shows top-3 and asks for
   a retake below 50 % confidence.
2. **18 of 38 classes, 6 crops** (apple, bell pepper, corn, grape, potato, tomato). Other
   crops are out of scope and the app does not pretend otherwise.
3. **Class imbalance in field data** — e.g. `potato_healthy` has a single test image, so its
   per-class score is indicative, not reliable.
4. **The gate can over-refuse.** ~1 % of genuine leaves are refused; the fix is to
   re-photograph with the leaf filling the frame in daylight.
5. **Advisory is decision support, not a substitute for an agronomist** — it is derived from
   published extension guidance, not field trials.
6. **Weather needs internet**; without it the app falls back to manual soil readings and
   says so on screen.

--- 

## 6. Demo video and deployed app

* **Demo video:** _〈https://drive.google.com/file/d/19Us3zN2I6sN1txOf_xZB1OPdydAFy3Qr/view?usp=drivesdk 〉
  
* **Deployed app:** _〈https://animated-space-adventure-wrwg7jp44qj939469-8000.app.github.dev/ 〉_
* may work on some devices only. If not working, you have to change your DNS Probe.

---

## Repository structure (7.2)

```
README.md              this file — the entry point
app/                   application source
  ├── backend/         FastAPI service (main.py) + the pre-built UI it serves
  └── frontend/        React + Vite source for the UI
model/                 model code and the required predict interface
  ├── best_model.pth   44 MB trained weights (committed; under GitHub's 100 MB limit)
  ├── inference.py     DiseaseClassifier — the predict() implementation
  ├── preprocess.py    transforms used at train and eval time
  ├── train.py         stage 1 (lab), dataset.py / evaluate.py
  └── class_names.json the 18 classes, in output order
predict.py             Section 4.1 CLI: python predict.py --image leaf.jpg
modules/               weather, irrigation, sustainability, assistant, crop recommender, i18n
report/                one-page model report (7.3) + metrics JSON + confusion matrix
requirements.txt       Python dependencies; run.sh / run.bat / run.ps1 install and launch
tests/                 460+ tests pinning the API, the UI contracts and the model interface
samples/               bundled leaf photos for a no-upload demo
```

## Retraining (optional)

Training is fully reproducible; the datasets download via the scripts and are not committed.

```bash
python scripts/download_datasets.py        # PlantVillage (HF mirror) + PlantDoc
python model/train.py                      # stage 1: lab pre-training
python model/evaluate.py --split val       # in-domain metrics
python model/evaluate.py --split test_field # honest field metrics
```

## Tests

```bash
python -m pytest -q tests/                 # API, UI contracts, model interface
bash run.sh --check-ui                     # headless checks of the shipped UI bundle
```
