"""Base retrieval interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from retrieval.models import MetadataFilterSpec, ProcessedQuery, ScoredChunkCandidate


class Retriever(ABC):
    """Base contract implemented by dense, keyword, and hybrid retrievers."""

    @abstractmethod
    def retrieve(
        self,
        query: ProcessedQuery,
        *,
        top_k: int,
        filters: MetadataFilterSpec | None = None,
        query_embedding: Sequence[float] | None = None,
        score_threshold: float | None = None,
    ) -> list[ScoredChunkCandidate]:
        raise NotImplementedError
