from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..schemas import DecisionResult, DiagnosisResult


def parse_diagnosis_payload(payload: Mapping[str, Any]) -> DiagnosisResult:
    """Normalize and validate a model-produced diagnosis payload."""
    reliability = _normalize_reliability(payload.get("reliability"))
    reason = _coerce_string(payload.get("reason"), "diagnosis reason was not provided")
    evidence_points = _coerce_string_list(payload.get("evidence_points"))
    risks = _coerce_string_list(payload.get("risks"))
    recommendations = _coerce_string_list(payload.get("recommendations"))
    confidence_score = _clamp_score(payload.get("confidence_score", 0.0))
    return DiagnosisResult(
        reliability=reliability,
        reason=reason,
        confidence_score=confidence_score,
        evidence_points=evidence_points,
        risks=risks,
        recommendations=recommendations,
    )


def parse_decision_payload(payload: Mapping[str, Any]) -> DecisionResult:
    """Normalize and validate a model-produced decision payload."""
    actions = _coerce_string_list(payload.get("actions"))
    return DecisionResult(
        harvest=_coerce_bool(payload.get("harvest")),
        fill_light=_coerce_bool(payload.get("fill_light")),
        manual_review=_coerce_bool(payload.get("manual_review")),
        message=_coerce_string(payload.get("message"), "no user-facing decision message was provided"),
        rationale=_coerce_string(payload.get("rationale"), ""),
        actions=actions,
    )


def _normalize_reliability(value: Any) -> str:
    normalized = _coerce_string(value, "medium").strip().lower()
    aliases = {
        "high": "high",
        "strong": "high",
        "medium": "medium",
        "mid": "medium",
        "moderate": "medium",
        "low": "low",
        "weak": "low",
    }
    return aliases.get(normalized, "medium")


def _coerce_string(value: Any, default: str) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else default
    if value is None:
        return default
    return str(value)


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        cleaned: list[str] = []
        for item in value:
            text = _coerce_string(item, "").strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned
    return [_coerce_string(value, "").strip()] if _coerce_string(value, "").strip() else []


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"1", "true", "yes", "y", "on"}
    return False


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(1.0, score))
