"""Scoring helpers for dense, keyword, and hybrid retrieval."""

from __future__ import annotations

import math
from typing import Mapping, Sequence


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError(
            f"Vector dimension mismatch: left={len(left)} right={len(right)}"
        )

    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def min_max_normalize(scores: Mapping[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    minimum = min(scores.values())
    maximum = max(scores.values())
    if math.isclose(minimum, maximum):
        return {key: (1.0 if value > 0 else 0.0) for key, value in scores.items()}
    return {key: (value - minimum) / (maximum - minimum) for key, value in scores.items()}


def weighted_sum(dense_score: float, keyword_score: float, dense_weight: float, keyword_weight: float) -> float:
    return (dense_score * dense_weight) + (keyword_score * keyword_weight)


def reciprocal_rank_score(rank: int | None, constant: int = 60) -> float:
    if rank is None:
        return 0.0
    return 1.0 / (constant + rank)


def validate_vector_dimension(vector: Sequence[float], expected_dimension: int | None) -> tuple[float, ...]:
    values = tuple(float(value) for value in vector)
    if expected_dimension is not None and len(values) != expected_dimension:
        raise ValueError(
            f"Embedding dimension mismatch: expected={expected_dimension} actual={len(values)}"
        )
    return values
