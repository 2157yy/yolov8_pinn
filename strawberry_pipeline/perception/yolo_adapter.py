from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

from ..interfaces import PerceptionModule
from ..schemas import (
    BoundingBox,
    DiseaseDetection,
    PerceptionResult,
    SceneSummary,
    StrawberryDetection,
)

# Default disease class names (from strawberry-1/data.yaml)
DEFAULT_DISEASE_NAMES: dict[int, str] = {
    0: "Angular Leafspot",
    1: "Anthracnose Fruit Rot",
    2: "Blossom Blight",
    3: "Gray Mold",
    4: "Leaf Spot",
    5: "Powdery Mildew Fruit",
    6: "Powdery Mildew Leaf",
}


def _compute_scene_summary(image: np.ndarray, metadata: dict[str, Any] | None = None) -> SceneSummary:
    """Derive basic scene-level features from the image for light/diagnosis context."""
    metadata = metadata or {}

    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    avg_light = float(np.mean(gray) / 255.0)

    hour = datetime.now().hour
    if 6 <= hour < 12:
        time_period = "morning"
    elif 12 <= hour < 17:
        time_period = "afternoon"
    elif 17 <= hour < 20:
        time_period = "evening"
    else:
        time_period = "night"

    return SceneSummary(
        avg_light=round(avg_light, 4),
        time_period=metadata.get("time_period", time_period),
        notes=metadata.get("scene_notes", ""),
    )


class YoloPerceptionAdapter(PerceptionModule):
    """Loads a YOLOv8 segmentation model and maps its output to the pipeline schema.

    Supports both strawberry disease detection (7-class) and generic COCO models.
    When a disease-specific model is loaded, results populate ``disease_detections``.
    The maturity-oriented ``detections`` list is reserved for a future maturity model
    and will be empty when only a disease model is provided.
    """

    def __init__(
        self,
        model_path: str | Path,
        disease_names: dict[int, str] | None = None,
        conf_threshold: float = 0.25,
        device: str | None = None,
    ) -> None:
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"YOLO model not found: {model_path}. "
                "Place a .pt weight file in the models/ directory."
            )

        self.model_path = model_path
        self.disease_names = disease_names or DEFAULT_DISEASE_NAMES
        self.conf_threshold = conf_threshold
        self._model = YOLO(str(model_path))
        if device is not None:
            self._model.to(device)

    # ------------------------------------------------------------------
    # PerceptionModule interface
    # ------------------------------------------------------------------

    def analyze(self, image: Any, metadata: dict[str, Any] | None = None) -> PerceptionResult:
        """Run YOLO inference on *image* and return structured results.

        *image* may be a file path (str/Path), a numpy array (HWC, BGR), or
        a PIL Image.  Metadata keys honoured:
        - ``image_id``, ``timestamp``, ``time_period``, ``scene_notes``
        """
        metadata = metadata or {}
        image_id = metadata.get("image_id", Path(str(image)).stem if isinstance(image, (str, Path)) else "image")
        timestamp = metadata.get("timestamp", datetime.now().isoformat())

        results = self._model.predict(source=image, conf=self.conf_threshold, verbose=False)
        result = results[0]

        scene_image = self._load_image_array(image)
        scene_summary = _compute_scene_summary(scene_image, metadata)

        disease_detections: list[DiseaseDetection] = []
        maturity_detections: list[StrawberryDetection] = []

        if result.boxes is not None:
            boxes_xyxy = result.boxes.xyxy
            classes = result.boxes.cls
            confs = result.boxes.conf

            for i in range(len(boxes_xyxy)):
                cls_id = int(classes[i].item())
                conf = float(confs[i].item())
                x1, y1, x2, y2 = boxes_xyxy[i].tolist()
                bbox = BoundingBox(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2))

                disease_name = self.disease_names.get(cls_id, f"class_{cls_id}")
                disease_detections.append(
                    DiseaseDetection(
                        bbox=bbox,
                        disease_class=cls_id,
                        disease_name=disease_name,
                        confidence=round(conf, 4),
                    )
                )

        return PerceptionResult(
            image_id=image_id,
            timestamp=timestamp,
            detections=maturity_detections,
            scene_summary=scene_summary,
            source=f"yolo_seg:{self.model_path.name}",
            disease_detections=disease_detections,
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_image_array(image: Any) -> np.ndarray:
        if isinstance(image, np.ndarray):
            return image
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                raise FileNotFoundError(f"Cannot read image from path: {image}")
            return img
        # PIL Image
        try:
            import PIL.Image

            if isinstance(image, PIL.Image.Image):
                return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        except ImportError:
            pass
        raise TypeError(f"Unsupported image type: {type(image)}")
