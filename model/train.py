#!/usr/bin/env python3
"""Train the AgriSmart crop-disease classifier (transfer learning).

Checkpointing rule: after every epoch we keep the weights with the best
**validation macro-F1** (not accuracy - the classes are imbalanced), written to
`model/best_model.pth` together with the class list so inference can never drift
out of sync with training.

CPU demo recipe (used for the shipped weights, 2-core sandbox):
    python model/train.py --data data/splits --model resnet18 \
        --img-size 192 --epochs 8 --batch-size 64 --workers 0
GPU full recipe:
    python model/train.py --model efficientnet_b0 --img-size 224 --epochs 20 \
        --batch-size 64 --lr 3e-4 --device cuda --train-per-class 0 --augment strong

Every run appends to `report/training_log.json` (args, per-epoch loss/F1/acc,
wall-clock, best epoch) so the report can quote exact numbers.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.dataset import class_names, make_loaders, seed_everything  # noqa: E402

SUPPORTED = ("resnet18", "resnet34", "resnet50", "efficientnet_b0", "mobilenet_v3_small")


def build_model(name: str, n_classes: int, pretrained: bool = True) -> nn.Module:
    from torchvision import models

    if name not in SUPPORTED:
        raise SystemExit(f"unknown --model {name}; choose from {SUPPORTED}")
    weights = "DEFAULT" if pretrained else None
    if name == "efficientnet_b0":
        m = models.efficientnet_b0(weights=weights)
        m.classifier[1] = nn.Linear(m.classifier[1].in_features, n_classes)
    elif name == "mobilenet_v3_small":
        m = models.mobilenet_v3_small(weights=weights)
        m.classifier[3] = nn.Linear(m.classifier[3].in_features, n_classes)
    else:
        fn = getattr(models, name)
        m = fn(weights=weights)
        m.fc = nn.Linear(m.fc.in_features, n_classes)
    return m


def evaluate_model(model: nn.Module, loader, device: str, n_classes: int) -> dict:
    model.eval()
    loss_fn = nn.CrossEntropyLoss()
    ys, ps, losses = [], [], []
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            out = model(x)
            losses.append(float(loss_fn(out, y).item()))
            ps += out.argmax(1).cpu().tolist()
            ys += y.cpu().tolist()
    labels = list(range(n_classes))
    return {
        "loss": round(float(np.mean(losses)) if losses else 0.0, 4),
        "accuracy": round(float(np.mean([a == b for a, b in zip(ys, ps)])) if ys else 0.0, 4),
        "macro_f1": round(float(f1_score(ys, ps, average="macro", labels=labels,
                                        zero_division=0)) if ys else 0.0, 4),
        "n": len(ys),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--data", default=str(ROOT / "data" / "splits"))
    ap.add_argument("--model", default="resnet18", choices=SUPPORTED)
    ap.add_argument("--img-size", type=int, default=192)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--label-smoothing", type=float, default=0.05)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--accum-steps", type=int, default=1,
                    help="gradient accumulation: effective batch = batch-size * accum-steps "
                         "(keeps the recipe reproducible on a low-RAM CPU box)")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--augment", default="standard", choices=("standard", "strong", "none"))
    ap.add_argument("--balanced", dest="balanced", action="store_true", default=True)
    ap.add_argument("--no-balanced", dest="balanced", action="store_false")
    ap.add_argument("--train-per-class", type=int, default=0,
                    help="cap the training set per class (0 = use every image present)")
    ap.add_argument("--patience", type=int, default=4, help="early stop after N epochs without gain")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pretrained", dest="pretrained", action="store_true", default=True)
    ap.add_argument("--scratch", dest="pretrained", action="store_false")
    ap.add_argument("--warm-backbone", default=None, metavar="CKPT",
                    help="start from another checkpoint's BACKBONE, keeping a fresh "
                         "classifier head - use when the class lists differ (e.g. moving "
                         "from the 18-class model to the 38-class one)")
    ap.add_argument("--init-from", default=None,
                    help="warm-start the weights from a checkpoint (fine-tuning / resuming a "
                         "killed run). Example: --init-from model/best_model.pth")
    ap.add_argument("--out", default=str(ROOT / "model" / "best_model.pth"))
    ap.add_argument("--tag", default="", help="free-text tag stored in the training log")
    ap.add_argument("--resume-state", default=None, metavar="PATH",
                    help="epoch-level resume file (default: <out> with _state.pt) so a killed "
                         "run continues from the last finished epoch instead of starting over")
    ap.add_argument("--no-resume", dest="resume", action="store_false", default=True,
                    help="ignore any previous state file and start fresh")
    a = ap.parse_args()

    seed_everything(a.seed)
    torch.set_num_threads(max(1, torch.get_num_threads()))
    device = a.device
    data_dir = Path(a.data)
    if not (data_dir / "train").is_dir():
        raise SystemExit(f"no training split at {data_dir / 'train'} - run "
                         f"scripts/prepare_data.py first")

    train_loader, val_loader, classes, train_ds, val_ds = make_loaders(
        data_dir, img_size=a.img_size, batch_size=a.batch_size, workers=a.workers,
        balanced=a.balanced, augment=a.augment, seed=a.seed,
    )
    warm_f1 = None  # set by --init-from; seeds the "best" bar so fine-tuning cannot regress it
    n_train, n_val = len(train_ds), len(val_ds)
    if a.train_per_class:
        print(f"note: --train-per-class {a.train_per_class} is informational here; trim the split "
              f"with scripts/prepare_data.py --train-per-class N for faster CPU runs")
    print(f"device={device} model={a.model} img={a.img_size} train={n_train} val={n_val} "
          f"classes={len(classes)} augment={a.augment} balanced={a.balanced}")
    if n_train == 0:
        raise SystemExit("training split is empty")

    model = build_model(a.model, len(classes), pretrained=a.pretrained).to(device)
    if a.warm_backbone:
        src = Path(a.warm_backbone)
        if not src.exists():
            raise SystemExit(f"--warm-backbone {src} not found")
        ckpt = torch.load(src, map_location="cpu", weights_only=False)
        state = ckpt.get("state_dict", ckpt)
        mine = model.state_dict()
        keep = {k: v for k, v in state.items()
                if k in mine and mine[k].shape == v.shape}       # backbone only, head dropped
        missing = [k for k in mine if k not in keep]
        model.load_state_dict(keep, strict=False)
        print(f"--warm-backbone: loaded {len(keep)}/{len(mine)} tensors from {src.name}; "
              f"fresh layers: {len(missing)} "
              f"(head: {[k for k in missing if 'fc' in k or 'classifier' in k]})", flush=True)
    if a.init_from:
        init_path = Path(a.init_from)
        if not init_path.exists():
            raise SystemExit(f"--init-from {init_path} not found")
        ckpt = torch.load(init_path, map_location=device, weights_only=False)
        if list(ckpt.get("classes", [])) != list(classes):
            raise SystemExit("checkpoint classes do not match this split - refusing to warm start")
        model.load_state_dict(ckpt["state_dict"])
        warm_f1 = ckpt.get("val_macro_f1")
        print(f"warm start: loaded weights from {init_path} (val macro-F1 {warm_f1}); "
              f"this run only overwrites the checkpoint when it beats that score")
    loss_fn = nn.CrossEntropyLoss(label_smoothing=a.label_smoothing)
    opt = AdamW(model.parameters(), lr=a.lr, weight_decay=a.weight_decay)
    sched = CosineAnnealingLR(opt, T_max=max(a.epochs, 1))
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    history, best_f1, best_epoch, since_best = [], float(warm_f1 if warm_f1 else -1.0), 0, 0
    start_epoch = 1
    state_path = Path(a.resume_state) if a.resume_state else out_path.with_name(out_path.stem + "_state.pt")
    if a.resume and state_path.exists():
        try:
            st = torch.load(state_path, map_location="cpu", weights_only=False)
            if list(st.get("classes", [])) == list(classes):
                model.load_state_dict(st["state_dict"])
                start_epoch = int(st.get("epoch", 0)) + 1
                history = st.get("history", [])
                if st.get("best_f1") is not None:
                    best_f1 = float(st["best_f1"])
                print(f"resumed from {state_path.name}: {start_epoch - 1} epoch(s) already done, "
                      f"continuing at epoch {start_epoch}", flush=True)
            else:
                print(f"{state_path.name} has a different class list - ignoring it", flush=True)
        except Exception as exc:                     # a truncated file must never block a run
            print(f"could not resume from {state_path.name} ({exc}) - starting fresh", flush=True)

    t_start = time.time()
    for epoch in range(start_epoch, a.epochs + 1):
        model.train()
        t0, running, seen, correct = time.time(), 0.0, 0, 0
        accum = max(1, a.accum_steps)
        for i, (x, y) in enumerate(train_loader, 1):
            x, y = x.to(device), y.to(device)
            out = model(x)
            loss = loss_fn(out, y) / accum
            loss.backward()
            if i % accum == 0 or i == len(train_loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
            running += float(loss.item()) * accum * y.size(0)
            seen += y.size(0)
            correct += int((out.argmax(1) == y).sum().item())
            del x, y, out, loss
            if i % 20 == 0 or i == len(train_loader):
                print(f"  epoch {epoch}/{a.epochs} step {i}/{len(train_loader)} "
                      f"loss {running / max(seen,1):.4f} acc {correct / max(seen,1):.3f}", flush=True)
        sched.step()
        train_metrics = {"loss": round(running / max(seen, 1), 4),
                         "accuracy": round(correct / max(seen, 1), 4)}
        val_metrics = evaluate_model(model, val_loader, device, len(classes))
        row = {"epoch": epoch, "train": train_metrics, "val": val_metrics,
               "lr": round(float(opt.param_groups[0]["lr"]), 6),
               "seconds": round(time.time() - t0, 1)}
        history.append(row)
        print(f"epoch {epoch}: train loss {train_metrics['loss']:.4f} acc "
              f"{train_metrics['accuracy']:.3f} | val loss {val_metrics['loss']:.4f} acc "
              f"{val_metrics['accuracy']:.3f} macroF1 {val_metrics['macro_f1']:.4f} "
              f"({row['seconds']}s)", flush=True)

        if val_metrics["macro_f1"] > best_f1:
            best_f1, best_epoch, since_best = val_metrics["macro_f1"], epoch, 0
            torch.save({
                "model_name": a.model, "state_dict": model.state_dict(),
                "classes": classes, "img_size": a.img_size, "n_classes": len(classes),
                "val_macro_f1": best_f1, "val": val_metrics, "epoch": epoch,
                "args": {k: v for k, v in vars(a).items()},
                "architecture": f"torchvision {a.model} (ImageNet pretrained)",
                "trained_on": "PlantVillage train split (CC-BY), PlantDoc never used",
            }, out_path)
            print(f"  saved best checkpoint -> {out_path} (val macro-F1 {best_f1:.4f})", flush=True)

        # Crash-safe progress: one small write per epoch means a sandbox recycle costs
        # minutes, not the whole run. `--no-resume` ignores it.
        try:
            torch.save({"state_dict": model.state_dict(), "classes": classes, "epoch": epoch,
                        "best_f1": best_f1, "history": history, "img_size": a.img_size},
                       state_path)
            print(f"  progress saved -> {state_path.name} (epoch {epoch})", flush=True)
        except Exception as exc:
            print(f"  could not save {state_path.name}: {exc}", flush=True)
        else:
            since_best += 1
            if a.patience and since_best >= a.patience:
                print(f"early stopping: no val macro-F1 gain for {a.patience} epochs")
                break

    elapsed = round(time.time() - t_start, 1)
    log_path = ROOT / "report" / "training_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if log_path.exists():
        try:
            entries = json.loads(log_path.read_text())
        except Exception:
            entries = []
    entries.append({
        "tag": a.tag or f"{a.model}-{a.img_size}px-{a.epochs}e",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_start)),
        "elapsed_s": elapsed, "device": device, "n_train": n_train, "n_val": n_val,
        "classes": classes, "history": history,
        "best_epoch": best_epoch, "best_val_macro_f1": round(best_f1, 4),
        "args": {k: v for k, v in vars(a).items() if k != "out"},
    })
    log_path.write_text(json.dumps(entries, indent=2))
    print(f"\nbest val macro-F1 {best_f1:.4f} at epoch {best_epoch} | total {elapsed}s")
    print(f"checkpoint  -> {out_path}")
    print(f"training log-> {log_path}")
    print(f"\nNext: python model/evaluate.py --split data/splits/test_field")
    return 0


if __name__ == "__main__":
    sys.exit(main())
