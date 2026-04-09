"""Abstract query processing interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod

from retrieval.models import ProcessedQuery


class QueryProcessor(ABC):
    """Transforms raw user input into a retrieval-ready query object."""

    @abstractmethod
    def process(self, query: str) -> ProcessedQuery:
        raise NotImplementedError
