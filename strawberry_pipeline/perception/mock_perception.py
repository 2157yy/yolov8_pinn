from __future__ import annotations

from datetime import datetime
from typing import Any

from ..interfaces import PerceptionModule
from ..schemas import BoundingBox, PerceptionResult, SceneSummary, StrawberryDetection


class MockPerceptionModule(PerceptionModule):
    """Example adapter showing how YOLO/PINN can be wrapped behind the interface."""

    def analyze(self, image: Any, metadata: dict[str, Any] | None = None) -> PerceptionResult:
        metadata = metadata or {}
        image_id = metadata.get("image_id", "demo_image")
        timestamp = metadata.get("timestamp", datetime.now().isoformat())
        return PerceptionResult(
            image_id=image_id,
            timestamp=timestamp,
            detections=[
                StrawberryDetection(
                    bbox=BoundingBox(120, 86, 214, 201),
                    maturity_raw=0.68,
                    maturity_corrected=0.81,
                    confidence=0.93,
                    light_features={"brightness": 0.42, "shadow_ratio": 0.31},
                )
            ],
            scene_summary=SceneSummary(avg_light=0.45, time_period="morning"),
            source="mock_yolo_pinn",
        )
