from __future__ import annotations

from ..interfaces import DecisionAgent, DiagnosisAgent, MemoryAgent
from ..schemas import (
    DecisionResult,
    DiagnosisResult,
    MemoryQuery,
    MemoryRecord,
    PerceptionResult,
)


class MockDiagnosisAgent(DiagnosisAgent):
    """Example diagnosis agent that can be replaced with a Qwen-backed implementation."""

    def diagnose(
        self,
        perception: PerceptionResult,
        history: list[MemoryRecord] | None = None,
    ) -> DiagnosisResult:
        history = history or []
        consistent_history = len(history) > 0
        reason = "light is stable and correction is consistent"
        if consistent_history:
            reason = f"{reason}; matched with {len(history)} historical records"
        return DiagnosisResult(
            reliability="high",
            reason=reason,
            confidence_score=0.90,
            evidence_points=[reason],
            risks=[],
            recommendations=["current observation can be used for harvest judgement"],
        )


class MockDecisionAgent(DecisionAgent):
    """Example decision agent that can be replaced with a Qwen-backed implementation."""

    def decide(
        self,
        perception: PerceptionResult,
        diagnosis: DiagnosisResult,
        history: list[MemoryRecord] | None = None,
    ) -> DecisionResult:
        best_score = max((d.maturity_corrected for d in perception.detections), default=0.0)
        harvest = best_score >= 0.8 and diagnosis.reliability == "high"
        return DecisionResult(
            harvest=harvest,
            fill_light=False,
            manual_review=diagnosis.reliability != "high",
            message="recommended for harvest" if harvest else "continue observation",
            rationale="mock decision generated for local integration testing",
            actions=["harvest"] if harvest else ["continue_observation"],
        )


class InMemoryMemoryAgent(MemoryAgent):
    """Minimal memory implementation for local development and interface verification."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def recall(self, query: MemoryQuery) -> list[MemoryRecord]:
        records = self._records
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
        self._records.append(record)
