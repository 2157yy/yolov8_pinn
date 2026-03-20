from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from ..interfaces import DecisionAgent, DiagnosisAgent
from ..qwen_client import QwenChatClient, QwenClientError
from ..schemas import DecisionResult, DiagnosisResult, MemoryRecord, PerceptionResult
from .decision_agent import RuleBasedDecisionAgent
from .diagnosis_agent import RuleBasedDiagnosisAgent
from .payload_parsers import parse_decision_payload, parse_diagnosis_payload


@dataclass(slots=True)
class QwenAgentSettings:
    history_limit: int = 5
    temperature: float = 0.1
    use_rule_fallback: bool = True


class QwenDiagnosisAgent(DiagnosisAgent):
    """Diagnosis agent backed by a Qwen chat model."""

    def __init__(
        self,
        client: QwenChatClient,
        settings: QwenAgentSettings | None = None,
        fallback_agent: DiagnosisAgent | None = None,
    ) -> None:
        self.client = client
        self.settings = settings or QwenAgentSettings()
        self.fallback_agent = fallback_agent or RuleBasedDiagnosisAgent()

    def diagnose(
        self,
        perception: PerceptionResult,
        history: list[MemoryRecord] | None = None,
    ) -> DiagnosisResult:
        history = history or []
        try:
            payload = self.client.complete_json(
                system_prompt=self._system_prompt(),
                user_prompt=self._user_prompt(perception=perception, history=history),
                temperature=self.settings.temperature,
            )
            return parse_diagnosis_payload(payload)
        except (QwenClientError, ValueError, TypeError, KeyError) as exc:
            if self.settings.use_rule_fallback and self.fallback_agent is not None:
                result = self.fallback_agent.diagnose(perception=perception, history=history)
                fallback_note = f"Qwen fallback triggered: {exc}"
                evidence = list(result.evidence_points)
                if fallback_note not in evidence:
                    evidence.append(fallback_note)
                return DiagnosisResult(
                    reliability=result.reliability,
                    reason=result.reason,
                    confidence_score=result.confidence_score,
                    evidence_points=evidence,
                    risks=result.risks,
                    recommendations=result.recommendations,
                )
            raise

    def _system_prompt(self) -> str:
        return (
            "You are an agricultural diagnosis agent for strawberry maturity assessment. "
            "You receive structured perception data from a YOLOv8 + PINN pipeline. "
            "Return only one JSON object. Do not include markdown. "
            "Required fields: reliability, confidence_score, reason, evidence_points, risks, recommendations. "
            "reliability must be one of: high, medium, low. "
            "confidence_score must be a number between 0 and 1. "
            "evidence_points, risks and recommendations must be arrays of short strings."
        )

    def _user_prompt(self, *, perception: PerceptionResult, history: list[MemoryRecord]) -> str:
        payload = {
            "task": "diagnose reliability and likely lighting-related error sources",
            "perception": asdict(perception),
            "history": [self._memory_record_to_prompt_dict(item) for item in history[-self.settings.history_limit :]],
            "output_contract": {
                "reliability": "high|medium|low",
                "confidence_score": 0.0,
                "reason": "short explanation",
                "evidence_points": ["evidence 1"],
                "risks": ["risk 1"],
                "recommendations": ["recommendation 1"],
            },
        }
        return json.dumps(payload, ensure_ascii=True, indent=2)

    @staticmethod
    def _memory_record_to_prompt_dict(record: MemoryRecord) -> dict[str, Any]:
        return {
            "image_id": record.image_id,
            "timestamp": record.timestamp,
            "perception": asdict(record.perception),
            "diagnosis": asdict(record.diagnosis),
            "decision": asdict(record.decision),
            "metadata": record.metadata,
        }


class QwenDecisionAgent(DecisionAgent):
    """Decision agent backed by a Qwen chat model."""

    def __init__(
        self,
        client: QwenChatClient,
        settings: QwenAgentSettings | None = None,
        fallback_agent: DecisionAgent | None = None,
    ) -> None:
        self.client = client
        self.settings = settings or QwenAgentSettings()
        self.fallback_agent = fallback_agent or RuleBasedDecisionAgent()

    def decide(
        self,
        perception: PerceptionResult,
        diagnosis: DiagnosisResult,
        history: list[MemoryRecord] | None = None,
    ) -> DecisionResult:
        history = history or []
        try:
            payload = self.client.complete_json(
                system_prompt=self._system_prompt(),
                user_prompt=self._user_prompt(perception=perception, diagnosis=diagnosis, history=history),
                temperature=self.settings.temperature,
            )
            return parse_decision_payload(payload)
        except (QwenClientError, ValueError, TypeError, KeyError) as exc:
            if self.settings.use_rule_fallback and self.fallback_agent is not None:
                result = self.fallback_agent.decide(perception=perception, diagnosis=diagnosis, history=history)
                actions = list(result.actions)
                fallback_action = "fallback_to_rule_decision"
                if fallback_action not in actions:
                    actions.append(fallback_action)
                rationale = result.rationale or ""
                if rationale:
                    rationale = f"{rationale}; Qwen fallback triggered: {exc}"
                else:
                    rationale = f"Qwen fallback triggered: {exc}"
                return DecisionResult(
                    harvest=result.harvest,
                    fill_light=result.fill_light,
                    manual_review=result.manual_review,
                    message=result.message,
                    rationale=rationale,
                    actions=actions,
                )
            raise

    def _system_prompt(self) -> str:
        return (
            "You are an agricultural decision agent for strawberry maturity management. "
            "You receive structured perception and diagnosis results. "
            "Return only one JSON object. Do not include markdown. "
            "Required fields: harvest, fill_light, manual_review, message, rationale, actions. "
            "harvest, fill_light and manual_review must be booleans. "
            "actions must be an array of short machine-readable action strings."
        )

    def _user_prompt(
        self,
        *,
        perception: PerceptionResult,
        diagnosis: DiagnosisResult,
        history: list[MemoryRecord],
    ) -> str:
        payload = {
            "task": "generate a user-facing agricultural recommendation",
            "perception": asdict(perception),
            "diagnosis": asdict(diagnosis),
            "history": [self._memory_record_to_prompt_dict(item) for item in history[-self.settings.history_limit :]],
            "output_contract": {
                "harvest": False,
                "fill_light": False,
                "manual_review": False,
                "message": "short user-facing recommendation",
                "rationale": "short decision rationale",
                "actions": ["continue_observation"],
            },
        }
        return json.dumps(payload, ensure_ascii=True, indent=2)

    @staticmethod
    def _memory_record_to_prompt_dict(record: MemoryRecord) -> dict[str, Any]:
        return {
            "image_id": record.image_id,
            "timestamp": record.timestamp,
            "diagnosis": asdict(record.diagnosis),
            "decision": asdict(record.decision),
            "metadata": record.metadata,
        }
