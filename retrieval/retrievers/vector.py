"""Dense vector retrieval implementation."""

from __future__ import annotations

from typing import Sequence

from retrieval.config import VectorRetrieverConfig
from retrieval.models import MetadataFilterSpec, ProcessedQuery, ScoredChunkCandidate
from retrieval.retrievers.base import Retriever
from retrieval.retrievers.store import VectorStore


class VectorRetriever(Retriever):
    """Top-k dense retrieval over the configured vector store."""

    def __init__(
        self,
        vector_store: VectorStore,
        config: VectorRetrieverConfig | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.config = config or VectorRetrieverConfig()

    def retrieve(
        self,
        query: ProcessedQuery,
        *,
        top_k: int,
        filters: MetadataFilterSpec | None = None,
        query_embedding: Sequence[float] | None = None,
        score_threshold: float | None = None,
    ) -> list[ScoredChunkCandidate]:
        del query
        if query_embedding is None:
            raise ValueError("VectorRetriever requires a query embedding")

        candidate_limit = max(top_k, self.config.candidate_pool_size)
        threshold = score_threshold if score_threshold is not None else self.config.score_threshold
        candidates = self.vector_store.search(
            query_embedding,
            top_k=candidate_limit,
            filters=filters,
        )
        if threshold is not None:
            candidates = [candidate for candidate in candidates if candidate.score >= threshold]
        return candidates[:top_k]
