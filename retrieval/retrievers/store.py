"""Vector-store abstractions and local in-memory implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Sequence

from retrieval.filters import MetadataFilter
from retrieval.models import MetadataFilterSpec, ScoredChunkCandidate, StoredChunk
from retrieval.utils import cosine_similarity


class VectorStore(ABC):
    """Dense index abstraction expected by the retrieval layer."""

    @property
    @abstractmethod
    def embedding_dimension(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_embedding: Sequence[float],
        *,
        top_k: int,
        filters: MetadataFilterSpec | None = None,
    ) -> list[ScoredChunkCandidate]:
        raise NotImplementedError

    @abstractmethod
    def get_chunks(self, chunk_ids: Sequence[str]) -> list[StoredChunk]:
        raise NotImplementedError

    @abstractmethod
    def iter_chunks(self, filters: MetadataFilterSpec | None = None) -> Iterable[StoredChunk]:
        raise NotImplementedError


class InMemoryVectorStore(VectorStore):
    """Reference local vector store for testing and small deployments."""

    def __init__(
        self,
        records: Sequence[StoredChunk],
        *,
        metadata_filter: MetadataFilter | None = None,
    ) -> None:
        if not records:
            raise ValueError("InMemoryVectorStore requires at least one StoredChunk")

        self._records = list(records)
        self._record_by_id = {
            self._require_chunk_id(record): record
            for record in self._records
        }
        self._embedding_dimension = len(self._records[0].embedding)
        self._metadata_filter = metadata_filter or MetadataFilter()
        for record in self._records:
            if len(record.embedding) != self._embedding_dimension:
                raise ValueError("All stored embeddings must have the same dimension")

    @property
    def embedding_dimension(self) -> int:
        return self._embedding_dimension

    def search(
        self,
        query_embedding: Sequence[float],
        *,
        top_k: int,
        filters: MetadataFilterSpec | None = None,
    ) -> list[ScoredChunkCandidate]:
        if len(query_embedding) != self._embedding_dimension:
            raise ValueError(
                f"Query embedding dimension mismatch: expected={self._embedding_dimension} actual={len(query_embedding)}"
            )

        scored: list[ScoredChunkCandidate] = []
        for record in self.iter_chunks(filters):
            similarity = cosine_similarity(query_embedding, record.embedding)
            scored.append(
                ScoredChunkCandidate(
                    record=record,
                    score=similarity,
                    dense_score=similarity,
                )
            )
        scored.sort(key=lambda candidate: candidate.score, reverse=True)
        return scored[:top_k]

    def get_chunks(self, chunk_ids: Sequence[str]) -> list[StoredChunk]:
        return [self._record_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in self._record_by_id]

    def iter_chunks(self, filters: MetadataFilterSpec | None = None) -> Iterable[StoredChunk]:
        for record in self._records:
            if self._metadata_filter.matches(record.metadata, filters):
                yield record

    @staticmethod
    def _require_chunk_id(record: StoredChunk) -> str:
        chunk_id = record.metadata.chunk_id
        if chunk_id is None:
            raise ValueError("StoredChunk.metadata.chunk_id must be set")
        return chunk_id
