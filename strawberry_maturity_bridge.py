#!/usr/bin/env python3
"""Bridge script for strawberry maturity detection — called by the Express backend.

Reads a JSON request from stdin, runs YOLO maturity inference (3-class:
halfripe / ripe / unripe), draws annotated bounding boxes on the image, and
returns the result as JSON (including a base64-encoded annotated image).

Input format::

    {
      "image_path": "/path/to/image.jpg",
      "model_path": "models/strawberry-maturity-s-best.pt",
      "conf_threshold": 0.25
    }

Output format::

    {
      "success": true,
      "data": {
        "image_id": "img_001",
        "detections": [
          {"class_id": 0, "class_name": "halfripe", "confidence": 0.87,
           "bbox": {"x1": 10, "y1": 20, "x2": 100, "y2": 150}}
        ],
        "counts": {"halfripe": 3, "ripe": 5, "unripe": 1},
        "annotated_image_base64": "..."
      }
    }
"""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# 3-class maturity labels
DEFAULT_MATURITY_NAMES: dict[int, str] = {
    0: "halfripe",
    1: "ripe",
    2: "unripe",
}

# BGR colours for drawing
MATURITY_COLORS: dict[str, tuple[int, int, int]] = {
    "halfripe": (0, 255, 255),   # yellow
    "ripe": (0, 255, 0),         # green
    "unripe": (0, 165, 255),     # orange
}

DEFAULT_MODEL_PATH = "models/strawberry-maturity-s-best.pt"
DEFAULT_CONF_THRESHOLD = 0.25


def load_model(model_path: str | Path) -> YOLO:
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Maturity model not found: {path}. "
            "Download a 3-class strawberry maturity YOLO weight and place it "
            "in the models/ directory."
        )
    return YOLO(str(path))


def run_maturity_inference(
    image_path: str,
    model: YOLO,
    conf_threshold: float,
    maturity_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Run maturity inference and return structured results."""
    names = maturity_names or DEFAULT_MATURITY_NAMES
    results = model.predict(source=image_path, conf=conf_threshold, verbose=False)
    result = results[0]

    detections: list[dict[str, Any]] = []
    counts: dict[str, int] = {v: 0 for v in names.values()}

    if result.boxes is not None:
        boxes_xyxy = result.boxes.xyxy
        classes = result.boxes.cls
        confs = result.boxes.conf

        for i in range(len(boxes_xyxy)):
            cls_id = int(classes[i].item())
            conf = float(confs[i].item())
            x1, y1, x2, y2 = boxes_xyxy[i].tolist()
            class_name = names.get(cls_id, f"class_{cls_id}")

            detections.append({
                "class_id": cls_id,
                "class_name": class_name,
                "confidence": round(conf, 4),
                "bbox": {
                    "x1": round(float(x1), 1),
                    "y1": round(float(y1), 1),
                    "x2": round(float(x2), 1),
                    "y2": round(float(y2), 1),
                },
            })
            counts[class_name] = counts.get(class_name, 0) + 1

    return {"detections": detections, "counts": counts}


def draw_annotations(
    image: np.ndarray,
    detections: list[dict[str, Any]],
) -> np.ndarray:
    """Draw bounding boxes and labels on a copy of *image*."""
    annotated = image.copy()
    for d in detections:
        b = d["bbox"]
        name = d["class_name"]
        conf = d["confidence"]
        color = MATURITY_COLORS.get(name, (255, 255, 255))

        pt1 = (int(b["x1"]), int(b["y1"]))
        pt2 = (int(b["x2"]), int(b["y2"]))
        cv2.rectangle(annotated, pt1, pt2, color, 2)

        label = f"{name} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(annotated, (pt1[0], pt1[1] - th - 6), (pt1[0] + tw + 6, pt1[1]), color, -1)
        cv2.putText(annotated, label, (pt1[0] + 3, pt1[1] - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    return annotated


def encode_annotated_image(image: np.ndarray) -> str:
    """Return base64 JPEG string for the annotated image."""
    _, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buf).decode("utf-8")


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print(json.dumps({"success": False, "error": "Empty stdin input"}))
        return 1

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {exc}"}))
        return 1

    image_path = payload.get("image_path", "")
    if not image_path or not Path(image_path).exists():
        print(json.dumps({"success": False, "error": f"Image not found: {image_path}"}))
        return 1

    model_path = payload.get("model_path", DEFAULT_MODEL_PATH)
    conf_threshold = float(payload.get("conf_threshold", DEFAULT_CONF_THRESHOLD))
    image_id = Path(image_path).stem

    try:
        model = load_model(model_path)
        inference = run_maturity_inference(image_path, model, conf_threshold)

        image = cv2.imread(image_path)
        if image is None:
            print(json.dumps({"success": False, "error": f"Cannot read image: {image_path}"}))
            return 1

        annotated = draw_annotations(image, inference["detections"])
        annotated_b64 = encode_annotated_image(annotated)

        print(json.dumps({
            "success": True,
            "data": {
                "image_id": image_id,
                "detections": inference["detections"],
                "counts": inference["counts"],
                "annotated_image_base64": annotated_b64,
                "model_path": str(Path(model_path)),
            },
        }, ensure_ascii=False))

    except FileNotFoundError as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        return 1
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"Maturity inference failed: {exc}"}))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
