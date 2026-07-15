#!/usr/bin/env python3
"""Train YOLOv8-seg on strawberry disease dataset.

Usage (on cloud GPU server):
    pip install ultralytics
    python train_yolo.py

The dataset (strawberry-1/) must be in the same directory as this script.
Output: best.pt (copy to models/ in the main project)
"""

from __future__ import annotations

from pathlib import Path
from ultralytics import YOLO

MODEL = "yolov8s-seg.pt"       # pretrained base (auto-downloaded)
DATA = "strawberry-1/data.yaml"
EPOCHS = 100
IMSZ = 512
BATCH = 16
DEVICE = 0                     # GPU 0; use "cpu" or "mps" if no CUDA
PROJECT = "runs"
NAME = "strawberry_disease"


def main() -> None:
    root = Path(__file__).resolve().parent

    if not (root / DATA).exists():
        raise FileNotFoundError(
            f"Dataset config not found: {root / DATA}. "
            "Make sure strawberry-1/ is in the same directory as this script."
        )

    # Ultralytics auto-downloads the pretrained .pt if not present
    model = YOLO(MODEL)

    model.train(
        data=str(root / DATA),
        epochs=EPOCHS,
        imgsz=IMSZ,
        batch=BATCH,
        device=DEVICE,
        project=str(root / PROJECT),
        name=NAME,
        patience=50,
        pretrained=True,
        optimizer="SGD",
        lr0=0.01,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.001,
    )

    best = root / PROJECT / NAME / "weights" / "best.pt"
    print(f"\nTraining complete. Best weights: {best}")
    print("Copy this file to your project's models/ directory.")


if __name__ == "__main__":
    main()
