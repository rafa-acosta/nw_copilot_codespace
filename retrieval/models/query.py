"""Query and request models for retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .filters import MetadataFilterSpec


class RetrievalMode(str, Enum):
    """Supported retrieval modes."""

    DENSE = "dense"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass(slots=True)
class QueryHints:
    """Structured hints extracted from the user query."""

    preferred_source_types: tuple[str, ...] = ()
    page_numbers: tuple[int, ...] = ()
    sheet_names: tuple[str, ...] = ()
    section_terms: tuple[str, ...] = ()
    json_paths: tuple[str, ...] = ()
    cisco_terms: tuple[str, ...] = ()


@dataclass(slots=True)
class ProcessedQuery:
    """Normalized query ready for embedding and lexical retrieval."""

    original_query: str
    normalized_query: str
    keyword_query: str
    tokens: tuple[str, ...]
    technical_terms: tuple[str, ...]
    quoted_phrases: tuple[str, ...]
    expansions: tuple[str, ...] = ()
    hints: QueryHints = field(default_factory=QueryHints)


@dataclass(slots=True)
class RetrievalRequest:
    """Input contract for the retrieval orchestration service."""

    query: str
    top_k: int | None = None
    mode: RetrievalMode | None = None
    filters: MetadataFilterSpec | None = None
    score_threshold: float | None = None
    debug: bool | None = None
