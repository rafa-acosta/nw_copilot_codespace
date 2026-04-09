"""Local embedding adapters for the GUI application."""

from __future__ import annotations

from collections import Counter
import hashlib
import math
from typing import Sequence

from retrieval.embedders import CallableQueryEmbedder, QueryEmbedder
from retrieval.utils import normalize_user_query, tokenize_preserving_technical


class HashingEmbeddingModel:
    """Deterministic local hashing embedder with technical-token preservation."""

    def __init__(self, dimension: int = 512) -> None:
        if dimension <= 0:
            raise ValueError("Embedding dimension must be positive")
        self.dimension = dimension

    def embed_text(self, text: str) -> tuple[float, ...]:
        normalized = normalize_user_query(text)
        tokens = list(tokenize_preserving_technical(normalized, minimum_length=2))
        if not tokens:
            return tuple(0.0 for _ in range(self.dimension))

        terms = Counter(tokens)
        for left, right in zip(tokens, tokens[1:]):
            terms[f"{left} {right}"] += 1

        vector = [0.0] * self.dimension
        for term, frequency in terms.items():
            digest = hashlib.blake2b(term.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], byteorder="big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + math.log(frequency)
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return tuple(0.0 for _ in range(self.dimension))
        return tuple(value / norm for value in vector)

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self.embed_text(text) for text in texts]

    def as_query_embedder(self) -> QueryEmbedder:
        return CallableQueryEmbedder(self.embed_text, expected_dimension=self.dimension)
