"""Embedding interfaces for retrieval queries."""

from __future__ import annotations

from abc import ABC, abstractmethod

from retrieval.models import ProcessedQuery


class QueryEmbedder(ABC):
    """Generates embeddings for normalized user queries."""

    @property
    @abstractmethod
    def embedding_dimension(self) -> int | None:
        raise NotImplementedError

    @abstractmethod
    def embed(self, query: ProcessedQuery) -> tuple[float, ...]:
        raise NotImplementedError
