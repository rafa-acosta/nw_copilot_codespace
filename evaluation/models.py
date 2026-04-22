"""Serializable models for demand-driven RAGAS evaluations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def utcnow_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO 8601 format."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class RagasEvaluationPayload:
    """Single assistant answer plus the original retrieval context needed by RAGAS."""

    user_input: str
    response: str
    retrieved_contexts: tuple[str, ...]
    retrieved_context_ids: tuple[str, ...] = ()
    retrieved_context_metadata: tuple[Mapping[str, Any], ...] = ()
    reference: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def with_reference(self, reference: str | None) -> "RagasEvaluationPayload":
        cleaned_reference = reference.strip() if reference else None
        return RagasEvaluationPayload(
            user_input=self.user_input,
            response=self.response,
            retrieved_contexts=self.retrieved_contexts,
            retrieved_context_ids=self.retrieved_context_ids,
            retrieved_context_metadata=self.retrieved_context_metadata,
            reference=cleaned_reference or self.reference,
            metadata=self.metadata,
        )


@dataclass(slots=True)
class RagasMetricResult:
    """Normalized result for one RAGAS metric."""

    name: str
    score: float | None
    reason: str | None = None
    error: str | None = None
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "reason": self.reason,
            "error": self.error,
            "skipped": self.skipped,
        }


@dataclass(slots=True)
class RagasEvaluationResult:
    """Result bundle returned to the GUI after an explicit evaluation request."""

    metrics: tuple[RagasMetricResult, ...]
    provider: str
    model: str
    embedding_model: str | None = None
    evaluated_at: str = field(default_factory=utcnow_iso)
    reference_provided: bool = False
    retrieved_context_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "embedding_model": self.embedding_model,
            "evaluated_at": self.evaluated_at,
            "reference_provided": self.reference_provided,
            "retrieved_context_count": self.retrieved_context_count,
            "metrics": [metric.to_dict() for metric in self.metrics],
        }
