"""Callable adapter for local embedding models."""

from __future__ import annotations

from typing import Callable, Sequence

from retrieval.embedders.base import QueryEmbedder
from retrieval.models import ProcessedQuery
from retrieval.utils import validate_vector_dimension


class CallableQueryEmbedder(QueryEmbedder):
    """Wraps any local embedding callable behind the retrieval interface."""

    def __init__(
        self,
        embedding_function: Callable[[str], Sequence[float]],
        *,
        expected_dimension: int | None = None,
    ) -> None:
        self._embedding_function = embedding_function
        self._embedding_dimension = expected_dimension

    @property
    def embedding_dimension(self) -> int | None:
        return self._embedding_dimension

    def embed(self, query: ProcessedQuery) -> tuple[float, ...]:
        vector = self._embedding_function(query.normalized_query)
        values = validate_vector_dimension(vector, self._embedding_dimension)
        if self._embedding_dimension is None:
            self._embedding_dimension = len(values)
        return values
