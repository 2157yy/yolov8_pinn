from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(slots=True)
class StrawberryDetection:
    bbox: BoundingBox
    maturity_raw: float
    maturity_corrected: float
    confidence: float
    light_features: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SceneSummary:
    avg_light: float
    time_period: str
    notes: str = ""


@dataclass(slots=True)
class PerceptionResult:
    image_id: str
    timestamp: str
    detections: list[StrawberryDetection]
    scene_summary: SceneSummary
    source: str = "yolo_pinn"


@dataclass(slots=True)
class DiagnosisResult:
    reliability: str
    reason: str
    confidence_score: float = 0.0
    evidence_points: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DecisionResult:
    harvest: bool
    fill_light: bool
    manual_review: bool
    message: str
    rationale: str = ""
    actions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MemoryQuery:
    plot_id: str | None = None
    plant_batch_id: str | None = None
    image_id: str | None = None
    top_k: int = 5


@dataclass(slots=True)
class MemoryRecord:
    image_id: str
    timestamp: str
    perception: PerceptionResult
    diagnosis: DiagnosisResult
    decision: DecisionResult
    metadata: dict[str, Any] = field(default_factory=dict)
