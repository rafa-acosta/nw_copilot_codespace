"""Production query processor with technical-token preservation."""

from __future__ import annotations

from retrieval.config import QueryProcessingConfig
from retrieval.models import ProcessedQuery
from retrieval.query_processing.base import QueryProcessor
from retrieval.utils import (
    extract_quoted_phrases,
    extract_technical_terms,
    infer_query_hints,
    normalize_for_lookup,
    normalize_user_query,
    tokenize_preserving_technical,
    unique_preserve_order,
)


DEFAULT_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "acl": ("access-list",),
    "bgp": ("router bgp", "border gateway protocol"),
    "ospf": ("router ospf", "open shortest path first"),
    "xlsx": ("excel", "spreadsheet"),
    "json": ("key path", "object field"),
}


class TechnicalQueryProcessor(QueryProcessor):
    """Normalizes queries without destroying structured technical syntax."""

    def __init__(self, config: QueryProcessingConfig | None = None) -> None:
        self.config = config or QueryProcessingConfig()

    def process(self, query: str) -> ProcessedQuery:
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        normalized_query = normalize_user_query(
            query,
            collapse=self.config.collapse_whitespace,
        )
        quoted_phrases = extract_quoted_phrases(normalized_query) if self.config.preserve_quoted_phrases else ()
        technical_terms = extract_technical_terms(normalized_query)
        tokens = tokenize_preserving_technical(
            normalized_query,
            minimum_length=self.config.minimum_token_length,
        )
        expansions = self._expand(tokens) if self.config.enable_query_expansion else ()
        hints = infer_query_hints(normalized_query, technical_terms)

        return ProcessedQuery(
            original_query=query,
            normalized_query=normalized_query,
            keyword_query=normalize_for_lookup(normalized_query)
            if self.config.casefold_for_keywords
            else normalized_query,
            tokens=tokens,
            technical_terms=technical_terms,
            quoted_phrases=quoted_phrases,
            expansions=expansions,
            hints=hints,
        )

    def _expand(self, tokens: tuple[str, ...]) -> tuple[str, ...]:
        expansions: list[str] = []
        for token in tokens:
            expansions.extend(DEFAULT_EXPANSIONS.get(token, ()))
        return unique_preserve_order(expansions)
