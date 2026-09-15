"""Dataset + transform factory shared by train/evaluate/inference.

Transforms (single source of truth - the report quotes this file)
----------------------------------------------------------------
train : RandomResizedCrop(img_size, scale=(0.7, 1.0)) -> HFlip -> RandomRotation(15)
        -> ColorJitter(0.25, 0.25, 0.2, 0.02)
        -> (optional) RandomGrayscale(0.05) -> (optional) RandomAffine(10, (0.05,0.05))
        -> GaussianBlur(kernel 3) -> ToTensor -> ImageNet normalise
eval  : Resize(int(img_size*1.14)) -> CenterCrop(img_size) -> ToTensor -> ImageNet normalise

The `--augment strong` flag in train.py turns on the optional steps; it is the
documented first knob for closing the lab->field gap (CONTINUE_HERE.md section 6).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def class_names(splits_dir: str | Path) -> list[str]:
    """Class list for a split: prefer model/class_names.json order, else folders."""
    root = Path(splits_dir)
    train_dir = root / "train" if (root / "train").is_dir() else root
    folders = sorted(d.name for d in train_dir.iterdir() if d.is_dir()) if train_dir.is_dir() else []
    meta = Path(__file__).resolve().parent / "class_names.json"
    if meta.exists():
        try:
            order = json.loads(meta.read_text()).get("order", [])
            ordered = [c for c in order if c in folders]
            extra = [c for c in folders if c not in ordered]
            if ordered:
                return ordered + extra
        except Exception:
            pass
    return folders


def build_transforms(img_size: int = 192, train: bool = True, augment: str = "standard"):
    """Return a torchvision transform pipeline. `augment` in {standard, strong, none}."""
    from torchvision import transforms

    if not train or augment == "none":
        return transforms.Compose([
            transforms.Resize(int(img_size * 1.14)),
            transforms.CenterCrop(img_size),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])

    steps = [
        transforms.RandomResizedCrop(img_size, scale=(0.7, 1.0), ratio=(0.8, 1.25)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.2, hue=0.02),
    ]
    if augment == "strong":
        # Domain-shift knobs: field photos vary in geometry, colour and focus.
        steps += [
            transforms.RandomApply([transforms.RandomAffine(degrees=10, translate=(0.06, 0.06))], p=0.4),
            transforms.RandomApply([transforms.RandomGrayscale(p=1.0)], p=0.05),
            transforms.RandomApply([transforms.GaussianBlur(3, sigma=(0.1, 1.4))], p=0.25),
        ]
    else:
        steps.append(transforms.RandomApply([transforms.GaussianBlur(3)], p=0.15))
    steps += [transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)]
    return transforms.Compose(steps)


def make_dataset(root: str | Path, img_size: int = 192, train: bool = True,
                 augment: str = "standard"):
    """ImageFolder dataset (torchvision) with the AgriSmart transforms."""
    from torchvision.datasets import ImageFolder
    return ImageFolder(str(root), transform=build_transforms(img_size, train, augment))


def make_loaders(splits_dir: str | Path, img_size: int = 192, batch_size: int = 64,
                 workers: int = 0, balanced: bool = True, augment: str = "standard",
                 seed: int = 42, val_batch_size: int | None = None):
    """Return (train_loader, val_loader, classes, train_ds, val_ds).

    `balanced=True` adds a WeightedRandomSampler so the per-class caps in
    prepare_data.py do not bias the loss toward the big classes.
    """
    import torch
    from torch.utils.data import DataLoader, WeightedRandomSampler

    root = Path(splits_dir)
    train_ds = make_dataset(root / "train", img_size, True, augment)
    val_root = root / "val" if (root / "val").is_dir() else root / "train"
    val_ds = make_dataset(val_root, img_size, False, "none")
    classes = train_ds.classes

    sampler = None
    if balanced:
        targets = [t for _, t in train_ds.samples]  # ImageFolder exposes (path, class_idx)
        counts = [0] * len(classes)
        for t in targets:
            counts[t] += 1
        weights = [1.0 / max(counts[t], 1) for t in targets]
        g = torch.Generator().manual_seed(seed)
        sampler = WeightedRandomSampler(weights, num_samples=len(targets), replacement=True, generator=g)

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=sampler is None, sampler=sampler,
        num_workers=workers, pin_memory=False, drop_last=False,
    )
    val_loader = DataLoader(
        val_ds, batch_size=val_batch_size or batch_size, shuffle=False,
        num_workers=workers, pin_memory=False,
    )
    return train_loader, val_loader, classes, train_ds, val_ds


def image_files(root: str | Path) -> list[tuple[str, str]]:
    """(path, class) pairs for a split - used by evaluate.py without ImageFolder."""
    root = Path(root)
    out: list[tuple[str, str]] = []
    for cdir in sorted(p for p in root.iterdir() if p.is_dir()):
        for f in sorted(cdir.iterdir()):
            if f.suffix.lower() in IMG_EXTS:
                out.append((str(f), cdir.name))
    return out


def seed_everything(seed: int = 42) -> None:
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
