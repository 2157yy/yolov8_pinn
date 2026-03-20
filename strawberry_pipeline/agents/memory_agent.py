from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ..interfaces import MemoryAgent
from ..schemas import (
    BoundingBox,
    DecisionResult,
    DiagnosisResult,
    MemoryQuery,
    MemoryRecord,
    PerceptionResult,
    SceneSummary,
    StrawberryDetection,
)


class JsonlMemoryAgent(MemoryAgent):
    """Persistent memory backed by a JSONL file for agent-side development."""

    def __init__(self, storage_path: str | Path) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.touch()

    def recall(self, query: MemoryQuery) -> list[MemoryRecord]:
        records = self._load_records()
        if query.image_id:
            records = [record for record in records if record.image_id != query.image_id]
        if query.plot_id:
            records = [record for record in records if record.metadata.get("plot_id") == query.plot_id]
        if query.plant_batch_id:
            records = [
                record for record in records if record.metadata.get("plant_batch_id") == query.plant_batch_id
            ]
        return records[-query.top_k :]

    def save(self, record: MemoryRecord) -> None:
        payload = self._record_to_dict(record)
        with self.storage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True))
            handle.write("\n")

    def _load_records(self) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        with self.storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                records.append(self._record_from_dict(payload))
        return records

    @staticmethod
    def _record_to_dict(record: MemoryRecord) -> dict:
        return asdict(record)

    @staticmethod
    def _record_from_dict(payload: dict) -> MemoryRecord:
        perception_payload = payload["perception"]
        detections = [
            StrawberryDetection(
                bbox=BoundingBox(**item["bbox"]),
                maturity_raw=item["maturity_raw"],
                maturity_corrected=item["maturity_corrected"],
                confidence=item["confidence"],
                light_features=item.get("light_features", {}),
            )
            for item in perception_payload.get("detections", [])
        ]
        perception = PerceptionResult(
            image_id=perception_payload["image_id"],
            timestamp=perception_payload["timestamp"],
            detections=detections,
            scene_summary=SceneSummary(**perception_payload["scene_summary"]),
            source=perception_payload.get("source", "yolo_pinn"),
        )
        diagnosis_payload = payload["diagnosis"]
        diagnosis = DiagnosisResult(
            reliability=diagnosis_payload["reliability"],
            reason=diagnosis_payload["reason"],
            confidence_score=diagnosis_payload.get("confidence_score", 0.0),
            evidence_points=diagnosis_payload.get("evidence_points", []),
            risks=diagnosis_payload.get("risks", []),
            recommendations=diagnosis_payload.get("recommendations", []),
        )
        decision_payload = payload["decision"]
        decision = DecisionResult(
            harvest=decision_payload["harvest"],
            fill_light=decision_payload["fill_light"],
            manual_review=decision_payload["manual_review"],
            message=decision_payload["message"],
            rationale=decision_payload.get("rationale", ""),
            actions=decision_payload.get("actions", []),
        )
        return MemoryRecord(
            image_id=payload["image_id"],
            timestamp=payload["timestamp"],
            perception=perception,
            diagnosis=diagnosis,
            decision=decision,
            metadata=payload.get("metadata", {}),
        )
