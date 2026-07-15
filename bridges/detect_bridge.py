#!/usr/bin/env python3
"""Bridge script for YOLO disease detection — called by the Express backend.

Reads a JSON request from stdin, runs YOLO inference (and optionally the full
strawberry pipeline), and writes a JSON response to stdout.

Input format::

    {
      "image_path": "/path/to/image.jpg",
      "model_path": "models/yolov8s-seg.pt",
      "conf_threshold": 0.25,
      "run_pipeline": false,
      "metadata": {
        "image_id": "img_001",
        "plot_id": "plot_a",
        "plant_batch_id": "batch_1"
      }
    }

Output format::

    {
      "success": true,
      "data": {
        "image_id": "img_001",
        "disease_detections": [...],
        "scene_summary": {...},
        "pipeline_output": null
      }
    }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the project root is on sys.path so strawberry_pipeline is importable
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        print(json.dumps({"success": False, "error": "Empty stdin input"}))
        sys.exit(1)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {exc}"}))
        sys.exit(1)

    image_path = payload.get("image_path", "")
    if not image_path or not Path(image_path).exists():
        print(json.dumps({"success": False, "error": f"Image not found: {image_path}"}))
        sys.exit(1)

    model_path = payload.get("model_path", "models/yolov8s-seg.pt")
    conf_threshold = float(payload.get("conf_threshold", 0.25))
    run_pipeline = bool(payload.get("run_pipeline", False))
    metadata = payload.get("metadata") or {}

    # ------------------------------------------------------------------
    # YOLO inference via the perception adapter
    # ------------------------------------------------------------------
    try:
        from strawberry_pipeline.perception.yolo_adapter import YoloPerceptionAdapter

        adapter = YoloPerceptionAdapter(
            model_path=model_path,
            conf_threshold=conf_threshold,
        )
        perception = adapter.analyze(image=image_path, metadata=metadata)
    except FileNotFoundError as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        sys.exit(1)
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"YOLO inference failed: {exc}"}))
        sys.exit(1)

    disease_detections = [
        {
            "disease_class": d.disease_class,
            "disease_name": d.disease_name,
            "confidence": d.confidence,
            "bbox": {"x1": d.bbox.x1, "y1": d.bbox.y1, "x2": d.bbox.x2, "y2": d.bbox.y2},
        }
        for d in perception.disease_detections
    ]

    # ------------------------------------------------------------------
    # Optional pipeline run
    # ------------------------------------------------------------------
    pipeline_output = None
    if run_pipeline:
        try:
            from strawberry_pipeline.examples import build_demo_pipeline

            pipeline = build_demo_pipeline()
            result = pipeline.run(image=image_path, metadata=metadata)
            pipeline_output = {
                "diagnosis": {
                    "reliability": result.diagnosis.reliability,
                    "confidence_score": result.diagnosis.confidence_score,
                    "reason": result.diagnosis.reason,
                    "risks": result.diagnosis.risks,
                },
                "decision": {
                    "harvest": result.decision.harvest,
                    "fill_light": result.decision.fill_light,
                    "manual_review": result.decision.manual_review,
                    "message": result.decision.message,
                },
            }
        except Exception as exc:
            pipeline_output = {"error": str(exc)}

    # ------------------------------------------------------------------
    # Response
    # ------------------------------------------------------------------
    result = {
        "success": True,
        "data": {
            "image_id": perception.image_id,
            "timestamp": perception.timestamp,
            "source": perception.source,
            "disease_detections": disease_detections,
            "detection_count": len(disease_detections),
            "scene_summary": {
                "avg_light": perception.scene_summary.avg_light,
                "time_period": perception.scene_summary.time_period,
                "notes": perception.scene_summary.notes,
            },
            "pipeline_output": pipeline_output,
        },
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
