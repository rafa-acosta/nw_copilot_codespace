"""Shared models for document and query domain routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_DOMAINS: tuple[str, ...] = ("general", "legal", "medical", "cisco")


@dataclass(slots=True)
class DomainDetectionResult:
    """Final domain classification result."""

    domain: str
    confidence: float
    reason: str
    scores: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.domain not in SUPPORTED_DOMAINS:
            raise ValueError(f"Unsupported domain: {self.domain}")
        self.confidence = max(0.0, min(float(self.confidence), 1.0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass(slots=True)
class DomainRouteDecision(DomainDetectionResult):
    """Resolved domain used at query time."""

    mode: str = "automatic"
    filter_applied: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "mode": self.mode,
                "filter_applied": self.filter_applied,
            }
        )
        return payload
