from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .interfaces import DecisionAgent, DiagnosisAgent, MemoryAgent, PerceptionModule
from .schemas import DecisionResult, DiagnosisResult, MemoryQuery, MemoryRecord, PerceptionResult


@dataclass
class PipelineOutput:
    perception: PerceptionResult
    diagnosis: DiagnosisResult
    decision: DecisionResult
    history: list[MemoryRecord]


class StrawberryPipeline:
    """High-level pipeline that depends on interfaces instead of concrete implementations."""

    def __init__(
        self,
        perception_module: PerceptionModule,
        diagnosis_agent: DiagnosisAgent,
        decision_agent: DecisionAgent,
        memory_agent: MemoryAgent,
    ) -> None:
        self.perception_module = perception_module
        self.diagnosis_agent = diagnosis_agent
        self.decision_agent = decision_agent
        self.memory_agent = memory_agent

    def run(self, image: Any, metadata: dict[str, Any] | None = None) -> PipelineOutput:
        metadata = metadata or {}
        history = self.memory_agent.recall(
            MemoryQuery(
                plot_id=metadata.get("plot_id"),
                plant_batch_id=metadata.get("plant_batch_id"),
                image_id=metadata.get("image_id"),
            )
        )
        perception = self.perception_module.analyze(image=image, metadata=metadata)
        diagnosis = self.diagnosis_agent.diagnose(perception=perception, history=history)
        decision = self.decision_agent.decide(
            perception=perception,
            diagnosis=diagnosis,
            history=history,
        )
        self.memory_agent.save(
            MemoryRecord(
                image_id=perception.image_id,
                timestamp=perception.timestamp,
                perception=perception,
                diagnosis=diagnosis,
                decision=decision,
                metadata=metadata,
            )
        )
        return PipelineOutput(
            perception=perception,
            diagnosis=diagnosis,
            decision=decision,
            history=history,
        )
