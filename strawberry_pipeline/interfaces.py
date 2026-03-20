from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .schemas import (
    DecisionResult,
    DiagnosisResult,
    MemoryQuery,
    MemoryRecord,
    PerceptionResult,
)


class PerceptionModule(ABC):
    """Interface for YOLO/PINN or any other perception backend."""

    @abstractmethod
    def analyze(self, image: Any, metadata: dict[str, Any] | None = None) -> PerceptionResult:
        """Return structured perception data for downstream agents."""


class DiagnosisAgent(ABC):
    """Interface for diagnosis logic based on perception output and memory context."""

    @abstractmethod
    def diagnose(
        self,
        perception: PerceptionResult,
        history: list[MemoryRecord] | None = None,
    ) -> DiagnosisResult:
        """Explain result reliability, risks and evidence."""


class DecisionAgent(ABC):
    """Interface for user-facing decision generation."""

    @abstractmethod
    def decide(
        self,
        perception: PerceptionResult,
        diagnosis: DiagnosisResult,
        history: list[MemoryRecord] | None = None,
    ) -> DecisionResult:
        """Generate harvest and farm-operation suggestions."""


class MemoryAgent(ABC):
    """Interface for pluggable memory storage implementations."""

    @abstractmethod
    def recall(self, query: MemoryQuery) -> list[MemoryRecord]:
        """Return historical context for the current sample."""

    @abstractmethod
    def save(self, record: MemoryRecord) -> None:
        """Persist the current round of pipeline output."""
