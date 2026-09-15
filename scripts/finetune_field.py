#!/usr/bin/env python3
"""Stage 2: field-domain adaptation of the PlantVillage model (v2).

The v1 model learned lab photos (PlantVillage: single leaf, uniform background)
and was then asked to read field photos (PlantDoc: cluttered, real light, real
phones). That gap - not the backbone, not the epoch count - is why its field
macro-F1 sat at 0.29 while its lab val was 0.99.

This script closes the gap the honest way:

  * init   : the shipped v1 checkpoint (ImageNet -> PlantVillage weights)
  * train  : PlantDoc **train** folder (field photos, 953 in our 18 classes)
             + a fresh PlantVillage replay draw every epoch, so the lab classes
             the field set does not contain (corn/potato healthy) are not
             forgotten and the net keeps its lesion vocabulary
  * select : macro-F1 on the PlantDoc train **holdout** (237 images) after every
             epoch - never on the test folder
  * report : PlantDoc **test** (128) and the 365-image holdout, scored once at
             the end by model/evaluate.py

Low-level layers (conv1/stem, layer1, layer2) are frozen: on ~1 k field images,
re-learning edge/colour filters is pure overfitting. layer3, layer4 and the head
are trained with a small LR, strong augmentation, label smoothing, weight EMA and
cosine decay.

Usage
-----
    python scripts/finetune_field.py                       # ~25 min on 2 CPU cores
    python scripts/finetune_field.py --epochs 20 --replay 3000
    python scripts/finetune_field.py --dry-run             # print the plan only
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIELD = ROOT / "data" / "splits_field"
PV = ROOT / "data" / "raw" / "plantvillage"
CKPT_IN = ROOT / "model" / "best_model.pth"
CKPT_OUT = ROOT / "model" / "best_model_field.pth"
CLASS_JSON = ROOT / "model" / "class_names.json"
IMG_EXTS = {".jpg", ".jpeg", ".png"}


# --------------------------------------------------------------------------- data
def class_order() -> list[str]:
    return list(json.loads(CLASS_JSON.read_text())["order"])


def index_folder(root: Path, order: list[str]) -> list[tuple[Path, int]]:
    idx = {c: i for i, c in enumerate(order)}
    out: list[tuple[Path, int]] = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if d.name not in idx:
            continue
        out += [(p, idx[d.name]) for p in sorted(d.iterdir()) if p.suffix.lower() in IMG_EXTS]
    return out


def lab_pool(order: list[str], val_per_class: int, seed: int):
    """PlantVillage images split once into (replay pool, never-trained lab val)."""
    rng = random.Random(seed)
    pool, val = [], []
    for d in sorted(p for p in PV.iterdir() if p.is_dir()):
        if d.name not in order:
            continue
        imgs = sorted(p for p in d.iterdir() if p.suffix.lower() in IMG_EXTS)
        rng.shuffle(imgs)
        val += [(p, order.index(d.name)) for p in imgs[:val_per_class]]
        pool += [(p, order.index(d.name)) for p in imgs[val_per_class:]]
    return pool, val


class ListDataset:
    """(path, label) list -> tensors, using the project's shared transforms."""

    def __init__(self, items, transform):
        self.items, self.transform = items, transform

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        from PIL import Image, ImageOps
        path, label = self.items[i]
        try:
            img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        except Exception:
            img = Image.new("RGB", (200, 200), (32, 90, 40))
        return self.transform(img), label


# -------------------------------------------------------------------------- train
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--replay", type=int, default=1900, help="PlantVillage images drawn per epoch")
    ap.add_argument("--batch-size", type=int, default=24)
    ap.add_argument("--lr-backbone", type=float, default=3e-4)
    ap.add_argument("--lr-head", type=float, default=1.5e-3)
    ap.add_argument("--wd", type=float, default=2e-4)
    ap.add_argument("--label-smoothing", type=float, default=0.05)
    ap.add_argument("--img-size", type=int, default=0, help="0 = keep the checkpoint's size")
    ap.add_argument("--lab-val-per-class", type=int, default=30)
    ap.add_argument("--freeze-until", default="layer2",
                    help="conv1|layer1|layer2|layer3|none - blocks at or before this stay frozen")
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--ema", type=float, default=0.995)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    # path overrides so the same stage-2 code can adapt any model/class set
    ap.add_argument("--field-split", default="data/splits_field",
                    help="folder holding train_field/ val_field/ (default: the 18-class split)")
    ap.add_argument("--lab-root", default="data/raw/plantvillage",
                    help="PlantVillage images, one folder per class (replay pool + lab val)")
    ap.add_argument("--init", default="model/best_model.pth", help="stage-1 checkpoint to adapt")
    ap.add_argument("--out", default="model/best_model_field.pth", help="adapted checkpoint to write")
    ap.add_argument("--class-names", default="model/class_names.json", help="class order file")
    ap.add_argument("--resume", dest="resume", action="store_true", default=True,
                    help="continue from model/_finetune_state.pt if present (default)")
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    ap.add_argument("--max-minutes", type=float, default=0,
                    help="stop cleanly after this many minutes of training (0 = no limit)")
    a = ap.parse_args()

    global FIELD, PV, CKPT_IN, CKPT_OUT, CLASS_JSON
    FIELD = ROOT / a.field_split
    PV = ROOT / a.lab_root
    CKPT_IN = ROOT / a.init
    CKPT_OUT = ROOT / a.out
    CLASS_JSON = ROOT / a.class_names

    import torch
    import torch.nn as nn
    torch.set_num_threads(a.threads)
    torch.manual_seed(a.seed)
    random.seed(a.seed)

    from model.dataset import build_transforms
    from model.train import build_model

    order = class_order()
    field_train = index_folder(FIELD / "train_field", order)
    field_val = index_folder(FIELD / "val_field", order)
    pool, lab_val = lab_pool(order, a.lab_val_per_class, a.seed)
    print(f"field train {len(field_train)} | field val {len(field_val)} | "
          f"lab replay pool {len(pool)} | lab val {len(lab_val)}", flush=True)

    ckpt = torch.load(CKPT_IN, map_location="cpu", weights_only=False)
    img_size = a.img_size or int(ckpt.get("img_size", 160))
    print(f"init: {CKPT_IN.name} ({ckpt.get('model_name')}, {img_size}px, "
          f"val macro-F1 {ckpt.get('val_macro_f1')})", flush=True)

    model = build_model(ckpt.get("model_name", "resnet18"), len(order), pretrained=False)
    model.load_state_dict(ckpt["state_dict"])

    # --- freeze the low-level blocks ----------------------------------------
    frozen = []
    blocks = [("conv1", model.conv1), ("bn1", model.bn1)] if hasattr(model, "conv1") else []
    blocks += [(f"layer{i+1}", layer) for i, layer in enumerate(model.layer4_list())] \
        if hasattr(model, "layer4_list") else \
        [(f"layer{i+1}", getattr(model, f"layer{i+1}")) for i in range(4)]
    stop = {"none": -1, "conv1": 0, "layer1": 1, "layer2": 2, "layer3": 3}.get(a.freeze_until, 2)
    for name, blk in blocks:
        if name in ("conv1", "bn1") or (name.startswith("layer") and stop >= int(name[-1])):
            for p in blk.parameters():
                p.requires_grad_(False)
            frozen.append(name)
    print(f"frozen blocks: {frozen or 'none'}", flush=True)

    head_params = list(model.fc.parameters())
    head_ids = {id(p) for p in head_params}
    backbone = [p for p in model.parameters() if p.requires_grad and id(p) not in head_ids]
    opt = torch.optim.AdamW([
        {"params": backbone, "lr": a.lr_backbone},
        {"params": head_params, "lr": a.lr_head},
    ], weight_decay=a.wd)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=[a.lr_backbone, a.lr_head],
        total_steps=max(1, a.epochs) * max(1, (len(field_train) + a.replay) // a.batch_size + 1),
        pct_start=0.15, div_factor=10, final_div_factor=20)
    crit = nn.CrossEntropyLoss(label_smoothing=a.label_smoothing)

    ema = copy.deepcopy(model).eval()
    for p in ema.parameters():
        p.requires_grad_(False)

    tf_train = build_transforms(img_size, train=True, augment="strong")
    from torchvision import transforms as T
    tf_train = T.Compose([tf_train, T.RandomErasing(p=0.25, scale=(0.02, 0.12))])
    tf_eval = build_transforms(img_size, train=False)

    if a.dry_run:
        print("dry run - plan only")
        return 0

    def evaluate(weights, items) -> tuple[float, float]:
        """(macro-F1, accuracy) for one weight set on one (path,label) list."""
        from sklearn.metrics import f1_score
        from torch.utils.data import DataLoader
        loader = DataLoader(ListDataset(items, tf_eval), batch_size=48, num_workers=0)
        ys, ps = [], []
        weights.eval()
        with torch.no_grad():
            for x, y in loader:
                ps += weights(x).argmax(1).tolist()
                ys += y.tolist()
        return (float(f1_score(ys, ps, average="macro", zero_division=0)), 
                float(sum(p == t for p, t in zip(ps, ys)) / max(1, len(ys))))

    STATE = CKPT_OUT.with_name(CKPT_OUT.stem + "_state.pt")

    def save_state(epoch, history, best, since_best):
        """Crash-safe: the box this runs on can be recycled mid-epoch."""
        tmp = STATE.with_suffix(".tmp")
        torch.save({"epoch": epoch, "history": history, "best": best,
                    "since_best": since_best, "model": model.state_dict(),
                    "ema": ema.state_dict(), "optimizer": opt.state_dict(),
                    "scheduler": sched.state_dict()}, tmp)
        tmp.replace(STATE)

    history, best = [], {"field_f1": -1.0}
    since_best, t_start = 0, time.time()
    start_epoch = 1
    if a.resume and STATE.exists():
        try:
            st = torch.load(STATE, map_location="cpu", weights_only=False)
            model.load_state_dict(st["model"])
            ema.load_state_dict(st["ema"])
            opt.load_state_dict(st["optimizer"])
            sched.load_state_dict(st["scheduler"])
            history, best = st["history"], st["best"]
            since_best, start_epoch = st["since_best"], int(st["epoch"]) + 1
            print(f"resumed from {STATE.name}: {len(history)} epochs done, "
                  f"best field-val macro-F1 {best['field_f1']:.4f}", flush=True)
        except Exception as exc:
            print(f"resume failed ({type(exc).__name__}: {exc}) - starting fresh", flush=True)

    for epoch in range(start_epoch, a.epochs + 1):
        if a.max_minutes and (time.time() - t_start) / 60 > a.max_minutes:
            print(f"time budget reached ({a.max_minutes} min) - stopping cleanly", flush=True)
            break
        # fresh PlantVillage replay draw each epoch -> the whole lab pool is seen
        rng = random.Random(a.seed + epoch)
        replay = rng.sample(pool, min(a.replay, len(pool)))
        items = field_train + replay
        rng.shuffle(items)
        loader = torch.utils.data.DataLoader(ListDataset(items, tf_train), batch_size=a.batch_size,
                                             shuffle=True, num_workers=0, drop_last=True)
        model.train()
        t0, seen, run_loss = time.time(), 0, 0.0
        for x, y in loader:
            opt.zero_grad(set_to_none=True)
            loss = crit(model(x), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 5.0)
            opt.step()
            sched.step()
            run_loss += float(loss.detach()) * len(y)
            seen += len(y)
            with torch.no_grad():
                d = a.ema
                for pe, pm in zip(ema.parameters(), model.parameters()):
                    pe.mul_(d).add_(pm, alpha=1 - d)
                for be, bm in zip(ema.buffers(), model.buffers()):
                    be.copy_(bm)
        f_f1, f_acc = evaluate(model, field_val)
        e_f1, _ = evaluate(ema, field_val)
        _, lab_acc = evaluate(ema, lab_val)
        row = {"epoch": epoch, "loss": round(run_loss / max(1, seen), 4),
               "field_val_macro_f1": round(f_f1, 4), "field_val_acc": round(f_acc, 4),
               "ema_field_val_macro_f1": round(e_f1, 4), "lab_val_acc": round(lab_acc, 4),
               "seconds": round(time.time() - t0, 1)}
        history.append(row)
        print(f"epoch {epoch:2d}: loss {row['loss']:.3f} | field-val macroF1 "
              f"{f_f1:.4f} (ema {e_f1:.4f}) acc {f_acc:.3f} | lab-val acc {lab_acc:.3f} "
              f"| {row['seconds']}s", flush=True)

        score = max(f_f1, e_f1)
        if score > best["field_f1"] + 1e-5:
            best = {"field_f1": score, "epoch": epoch,
                    "weights": "ema" if e_f1 >= f_f1 else "model", "lab_val_acc": lab_acc,
                    "field_val_acc": f_acc}
            src = ema if e_f1 >= f_f1 else model
            torch.save({
                "model_name": ckpt.get("model_name", "resnet18"),
                "state_dict": src.state_dict(),
                "classes": order, "img_size": img_size, "n_classes": len(order),
                "val_macro_f1": ckpt.get("val_macro_f1"),          # lab val, from stage 1
                "field_val_macro_f1": best["field_f1"],
                "val": {"lab_accuracy": lab_acc, "field_accuracy": f_acc,
                        "field_macro_f1": best["field_f1"]},
                "epoch": epoch,
                "architecture": ckpt.get("architecture", "torchvision resnet18"),
                "training_stage": ("stage 2 - field adaptation on PlantDoc train (+ PlantVillage "
                                   "replay); epoch picked on PlantDoc train holdout; PlantDoc "
                                   "test never used"),
                "args": {k: v for k, v in vars(a).items()},
                "stage2_history": history,
            }, CKPT_OUT)
            since_best = 0
            print(f"   saved -> {CKPT_OUT.name} (score {score:.4f}, {best['weights']})", flush=True)
        else:
            since_best += 1
            if since_best >= a.patience:
                save_state(epoch, history, best, since_best)
                print(f"early stop: no improvement for {a.patience} epochs", flush=True)
                break
        save_state(epoch, history, best, since_best)

    (ROOT / "report" / "finetune_log.json").write_text(json.dumps(
        {"init": str(CKPT_IN.name), "img_size": img_size, "frozen": frozen,
         "config": {k: v for k, v in vars(a).items()},
         "field_train": len(field_train), "replay_per_epoch": a.replay,
         "lab_val": len(lab_val), "history": history, "best": best,
         "minutes": round((time.time() - t_start) / 60, 1)}, indent=2))
    print(f"\nbest: field-val macro-F1 {best['field_f1']:.4f} @ epoch {best['epoch']} "
          f"({best['weights']}) after {(time.time() - t_start) / 60:.1f} min")
    print("next: python model/evaluate.py --split data/splits_field/test_field "
          "--checkpoint model/best_model_field.pth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
