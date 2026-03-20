from __future__ import annotations

from dataclasses import dataclass

from ..interfaces import DiagnosisAgent
from ..schemas import DiagnosisResult, MemoryRecord, PerceptionResult


@dataclass(slots=True)
class DiagnosisPolicy:
    low_light_threshold: float = 0.30
    bright_light_threshold: float = 0.80
    shadow_ratio_threshold: float = 0.45
    correction_gap_threshold: float = 0.15
    low_confidence_threshold: float = 0.60
    high_confidence_threshold: float = 0.85
    stable_history_gap_threshold: float = 0.10


class RuleBasedDiagnosisAgent(DiagnosisAgent):
    """Diagnose reliability and likely error sources from perception output and history."""

    def __init__(self, policy: DiagnosisPolicy | None = None) -> None:
        self.policy = policy or DiagnosisPolicy()

    def diagnose(
        self,
        perception: PerceptionResult,
        history: list[MemoryRecord] | None = None,
    ) -> DiagnosisResult:
        history = history or []
        detections = perception.detections
        if not detections:
            return DiagnosisResult(
                reliability="low",
                reason="no strawberry detections were produced by the perception module",
                confidence_score=0.10,
                evidence_points=["no valid detections are available for diagnosis"],
                risks=["missing target objects"],
                recommendations=["capture another image from a closer angle"],
            )

        avg_confidence = sum(item.confidence for item in detections) / len(detections)
        avg_gap = sum(abs(item.maturity_corrected - item.maturity_raw) for item in detections) / len(detections)
        avg_brightness = self._average_numeric_light_feature(detections, "brightness", perception.scene_summary.avg_light)
        avg_shadow_ratio = self._average_numeric_light_feature(detections, "shadow_ratio", 0.0)

        risks: list[str] = []
        recommendations: list[str] = []
        evidence: list[str] = []
        reliability_score = 1.0

        evidence.append(f"average confidence={avg_confidence:.2f}")
        evidence.append(f"average correction gap={avg_gap:.2f}")
        evidence.append(f"scene light={avg_brightness:.2f}")

        if avg_confidence < self.policy.low_confidence_threshold:
            reliability_score -= 0.35
            risks.append("low detection confidence")
            recommendations.append("re-capture the image or request manual review")
        elif avg_confidence >= self.policy.high_confidence_threshold:
            evidence.append("detection confidence is consistently high")

        if avg_gap > self.policy.correction_gap_threshold:
            reliability_score -= 0.20
            risks.append("large raw-to-corrected maturity gap")
            recommendations.append("verify whether lighting conditions are distorting maturity judgement")
            evidence.append("PINN correction changed the maturity estimate significantly")

        if avg_brightness < self.policy.low_light_threshold:
            reliability_score -= 0.20
            risks.append("low-light observation")
            recommendations.append("capture again under stronger natural light or add fill light")
        elif avg_brightness > self.policy.bright_light_threshold:
            reliability_score -= 0.10
            risks.append("over-bright observation")
            recommendations.append("check for direct glare or harsh sunlight")

        if avg_shadow_ratio > self.policy.shadow_ratio_threshold:
            reliability_score -= 0.15
            risks.append("heavy shadow coverage")
            recommendations.append("adjust camera angle to reduce shadowed areas")

        history_note = self._analyze_history(perception=perception, history=history)
        if history_note is not None:
            evidence.append(history_note["evidence"])
            reliability_score += history_note["score_delta"]
            if history_note["risk"]:
                risks.append(history_note["risk"])
            if history_note["recommendation"]:
                recommendations.append(history_note["recommendation"])

        reliability = self._to_reliability_label(reliability_score)
        reason = "; ".join(evidence)
        return DiagnosisResult(
            reliability=reliability,
            reason=reason,
            confidence_score=self._clamp_score(reliability_score),
            evidence_points=self._deduplicate(evidence),
            risks=self._deduplicate(risks),
            recommendations=self._deduplicate(recommendations),
        )

    def _analyze_history(
        self,
        perception: PerceptionResult,
        history: list[MemoryRecord],
    ) -> dict[str, str | float | None] | None:
        if not history:
            return None

        current_score = self._average_corrected_maturity(perception)
        historical_scores = [
            self._average_corrected_maturity(record.perception) for record in history if record.perception.detections
        ]
        if not historical_scores:
            return None

        historical_avg = sum(historical_scores) / len(historical_scores)
        gap = abs(current_score - historical_avg)
        if gap <= self.policy.stable_history_gap_threshold:
            return {
                "evidence": f"historical maturity trend is stable across {len(historical_scores)} records",
                "score_delta": 0.10,
                "risk": None,
                "recommendation": None,
            }
        return {
            "evidence": f"current maturity differs from history by {gap:.2f}",
            "score_delta": -0.10,
            "risk": "current observation deviates from recent history",
            "recommendation": "review recent images or re-check the current sample",
        }

    @staticmethod
    def _average_corrected_maturity(perception: PerceptionResult) -> float:
        if not perception.detections:
            return 0.0
        return sum(item.maturity_corrected for item in perception.detections) / len(perception.detections)

    @staticmethod
    def _average_numeric_light_feature(
        detections,
        feature_name: str,
        default: float,
    ) -> float:
        values = []
        for detection in detections:
            value = detection.light_features.get(feature_name)
            if isinstance(value, (int, float)):
                values.append(float(value))
        if not values:
            return default
        return sum(values) / len(values)

    @staticmethod
    def _to_reliability_label(score: float) -> str:
        if score >= 0.80:
            return "high"
        if score >= 0.55:
            return "medium"
        return "low"

    @staticmethod
    def _clamp_score(score: float) -> float:
        return max(0.0, min(1.0, score))

    @staticmethod
    def _deduplicate(items: list[str]) -> list[str]:
        ordered: list[str] = []
        for item in items:
            if item and item not in ordered:
                ordered.append(item)
        return ordered
