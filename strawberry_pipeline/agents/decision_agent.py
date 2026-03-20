from __future__ import annotations

from dataclasses import dataclass

from ..interfaces import DecisionAgent
from ..schemas import DecisionResult, DiagnosisResult, MemoryRecord, PerceptionResult


@dataclass(slots=True)
class DecisionPolicy:
    harvest_threshold: float = 0.80
    observe_threshold: float = 0.60
    low_light_threshold: float = 0.30


class RuleBasedDecisionAgent(DecisionAgent):
    """Convert diagnosis results into clear farm-operation recommendations."""

    def __init__(self, policy: DecisionPolicy | None = None) -> None:
        self.policy = policy or DecisionPolicy()

    def decide(
        self,
        perception: PerceptionResult,
        diagnosis: DiagnosisResult,
        history: list[MemoryRecord] | None = None,
    ) -> DecisionResult:
        history = history or []
        avg_maturity = self._average_corrected_maturity(perception)
        scene_light = perception.scene_summary.avg_light
        reliability = diagnosis.reliability

        manual_review = reliability == "low" or not perception.detections
        fill_light = scene_light < self.policy.low_light_threshold or "low-light observation" in diagnosis.risks

        if manual_review:
            return DecisionResult(
                harvest=False,
                fill_light=fill_light,
                manual_review=True,
                message=self._build_manual_review_message(avg_maturity, diagnosis),
                rationale="diagnosis reliability is too low for an automatic harvest recommendation",
                actions=self._build_actions(
                    harvest=False,
                    fill_light=fill_light,
                    manual_review=True,
                    continue_observation=False,
                ),
            )

        if avg_maturity >= self.policy.harvest_threshold and reliability in {"high", "medium"}:
            return DecisionResult(
                harvest=True,
                fill_light=fill_light and reliability != "high",
                manual_review=False,
                message=self._build_harvest_message(avg_maturity, history),
                rationale="corrected maturity is above the harvest threshold and diagnosis is acceptable",
                actions=self._build_actions(
                    harvest=True,
                    fill_light=fill_light and reliability != "high",
                    manual_review=False,
                    continue_observation=False,
                ),
            )

        if avg_maturity >= self.policy.observe_threshold:
            return DecisionResult(
                harvest=False,
                fill_light=fill_light,
                manual_review=reliability == "medium",
                message=self._build_observe_message(avg_maturity, diagnosis),
                rationale="the fruit is approaching harvest range but still benefits from another observation cycle",
                actions=self._build_actions(
                    harvest=False,
                    fill_light=fill_light,
                    manual_review=reliability == "medium",
                    continue_observation=True,
                ),
            )

        return DecisionResult(
            harvest=False,
            fill_light=fill_light,
            manual_review=False,
            message=self._build_wait_message(avg_maturity),
            rationale="corrected maturity remains below the observation threshold",
            actions=self._build_actions(
                harvest=False,
                fill_light=fill_light,
                manual_review=False,
                continue_observation=True,
            ),
        )

    @staticmethod
    def _average_corrected_maturity(perception: PerceptionResult) -> float:
        if not perception.detections:
            return 0.0
        return sum(item.maturity_corrected for item in perception.detections) / len(perception.detections)

    @staticmethod
    def _build_manual_review_message(avg_maturity: float, diagnosis: DiagnosisResult) -> str:
        return (
            f"manual review is recommended before harvest; "
            f"estimated corrected maturity={avg_maturity:.2f}, reliability={diagnosis.reliability}"
        )

    @staticmethod
    def _build_harvest_message(avg_maturity: float, history: list[MemoryRecord]) -> str:
        if history:
            return (
                f"recommended for harvest; corrected maturity={avg_maturity:.2f}, "
                f"supported by {len(history)} historical records"
            )
        return f"recommended for harvest; corrected maturity={avg_maturity:.2f}"

    @staticmethod
    def _build_observe_message(avg_maturity: float, diagnosis: DiagnosisResult) -> str:
        return (
            f"continue close observation; corrected maturity={avg_maturity:.2f}, "
            f"reliability={diagnosis.reliability}"
        )

    @staticmethod
    def _build_wait_message(avg_maturity: float) -> str:
        return f"not ready for harvest yet; corrected maturity={avg_maturity:.2f}"

    @staticmethod
    def _build_actions(
        *,
        harvest: bool,
        fill_light: bool,
        manual_review: bool,
        continue_observation: bool,
    ) -> list[str]:
        actions: list[str] = []
        if harvest:
            actions.append("harvest")
        if fill_light:
            actions.append("fill_light")
        if manual_review:
            actions.append("manual_review")
        if continue_observation:
            actions.append("continue_observation")
        if not actions:
            actions.append("no_action")
        return actions
