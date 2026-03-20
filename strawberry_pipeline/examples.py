from __future__ import annotations

from pathlib import Path

from .agents import JsonlMemoryAgent, RuleBasedDecisionAgent, RuleBasedDiagnosisAgent
from .orchestrator import StrawberryPipeline
from .perception import MockPerceptionModule
from .qwen_client import QwenChatClient


def build_demo_pipeline(storage_path: str | Path = "memory/strawberry_pipeline.jsonl") -> StrawberryPipeline:
    return StrawberryPipeline(
        perception_module=MockPerceptionModule(),
        diagnosis_agent=RuleBasedDiagnosisAgent(),
        decision_agent=RuleBasedDecisionAgent(),
        memory_agent=JsonlMemoryAgent(storage_path=storage_path),
    )


def build_qwen_pipeline(
    client: QwenChatClient,
    storage_path: str | Path = "memory/strawberry_pipeline.jsonl",
) -> StrawberryPipeline:
    from .agents import QwenDecisionAgent, QwenDiagnosisAgent

    return StrawberryPipeline(
        perception_module=MockPerceptionModule(),
        diagnosis_agent=QwenDiagnosisAgent(client=client),
        decision_agent=QwenDecisionAgent(client=client),
        memory_agent=JsonlMemoryAgent(storage_path=storage_path),
    )
