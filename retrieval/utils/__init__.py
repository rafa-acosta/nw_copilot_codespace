"""Utility exports for retrieval."""

from .logging import configure_logger
from .scoring import cosine_similarity, min_max_normalize, reciprocal_rank_score, validate_vector_dimension, weighted_sum
from .text import (
    collapse_whitespace,
    contains_term,
    extract_quoted_phrases,
    extract_sheet_headers,
    extract_technical_terms,
    infer_query_hints,
    normalize_for_lookup,
    normalize_unicode,
    normalize_user_query,
    tokenize_preserving_technical,
    unique_preserve_order,
)
from .timing import StageTimer

__all__ = [
    "StageTimer",
    "collapse_whitespace",
    "configure_logger",
    "contains_term",
    "cosine_similarity",
    "extract_quoted_phrases",
    "extract_sheet_headers",
    "extract_technical_terms",
    "infer_query_hints",
    "min_max_normalize",
    "normalize_for_lookup",
    "normalize_unicode",
    "normalize_user_query",
    "reciprocal_rank_score",
    "tokenize_preserving_technical",
    "unique_preserve_order",
    "validate_vector_dimension",
    "weighted_sum",
]
