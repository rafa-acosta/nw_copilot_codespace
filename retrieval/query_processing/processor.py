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
    "access-list": ("acl",),
    "bgp": ("router bgp", "border gateway protocol"),
    "border": ("bgp",),
    "ospf": ("router ospf", "open shortest path first"),
    "vlan": ("switchport", "trunk allowed vlan"),
    "interface": ("port", "gigabitethernet"),
    "xlsx": ("excel", "spreadsheet"),
    "xls": ("excel", "spreadsheet"),
    "csv": ("spreadsheet", "table"),
    "json": ("key path", "object field"),
    "pdf": ("page", "document"),
    "docx": ("word", "document"),
    "contrato": ("contract", "agreement"),
    "contract": ("contrato", "agreement"),
    "factura": ("invoice", "bill"),
    "invoice": ("factura", "bill"),
    "medico": ("medical", "health"),
    "medical": ("medico", "health"),
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
        expansions = self._expand(tokens)
        if not self.config.enable_query_expansion:
            expansions = ()
        variants = self._variants(normalized_query, tokens, technical_terms, expansions)
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
            variants=variants,
            hints=hints,
        )

    def _expand(self, tokens: tuple[str, ...]) -> tuple[str, ...]:
        expansions: list[str] = []
        for token in tokens:
            expansions.extend(DEFAULT_EXPANSIONS.get(token, ()))
        return unique_preserve_order(expansions)

    def _variants(
        self,
        normalized_query: str,
        tokens: tuple[str, ...],
        technical_terms: tuple[str, ...],
        expansions: tuple[str, ...],
    ) -> tuple[str, ...]:
        variants: list[str] = []
        variants.extend(expansions)

        if technical_terms:
            variants.append(" ".join(technical_terms))

        if expansions:
            variants.append(" ".join((*tokens, *expansions)))

        compact_terms = [term for term in (*tokens, *technical_terms) if len(term) >= self.config.minimum_token_length]
        if compact_terms:
            variants.append(" ".join(compact_terms))

        cleaned = [
            variant
            for variant in unique_preserve_order(variants)
            if variant and normalize_for_lookup(variant) != normalize_for_lookup(normalized_query)
        ]
        return tuple(cleaned[: max(self.config.max_query_variants, 0)])
