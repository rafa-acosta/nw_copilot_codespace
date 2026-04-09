"""Timing helpers for traceable retrieval execution."""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Iterator


class StageTimer:
    """Collects per-stage latency metrics for a retrieval request."""

    def __init__(self) -> None:
        self._started_at = perf_counter()
        self.steps: dict[str, float] = {}

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        started_at = perf_counter()
        try:
            yield
        finally:
            self.steps[name] = (perf_counter() - started_at) * 1000.0

    @property
    def total_ms(self) -> float:
        return (perf_counter() - self._started_at) * 1000.0
