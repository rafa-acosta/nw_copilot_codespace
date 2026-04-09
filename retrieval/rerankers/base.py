"""Base reranker interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from retrieval.models import ProcessedQuery, ScoredChunkCandidate


class Reranker(ABC):
    """Improves ordering after candidate retrieval."""

    @abstractmethod
    def rerank(
        self,
        query: ProcessedQuery,
        candidates: Sequence[ScoredChunkCandidate],
        *,
        top_k: int,
    ) -> list[ScoredChunkCandidate]:
        raise NotImplementedError
