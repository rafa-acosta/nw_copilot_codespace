"""Result models for intermediate and final retrieval outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .records import StoredChunk


@dataclass(slots=True)
class RetrievalTraceStep:
    """Traceable step in the retrieval pipeline."""

    name: str
    duration_ms: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScoredChunkCandidate:
    """Internal candidate representation shared across retrieval stages."""

    record: StoredChunk
    score: float
    dense_score: float | None = None
    keyword_score: float | None = None
    fused_score: float | None = None
    rerank_score: float | None = None
    matched_terms: tuple[str, ...] = ()
    applied_boosts: tuple[str, ...] = ()

    @property
    def chunk_id(self) -> str:
        chunk_id = self.record.metadata.chunk_id
        if chunk_id is None:
            raise ValueError("Chunk metadata.chunk_id must be populated")
        return chunk_id


@dataclass(slots=True)
class RetrievedChunk:
    """User-facing retrieved chunk."""

    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any]
    source_type: str
    dense_score: float | None = None
    keyword_score: float | None = None
    rerank_score: float | None = None
    matched_terms: tuple[str, ...] = ()
    applied_boosts: tuple[str, ...] = ()


@dataclass(slots=True)
class RetrievalTiming:
    """Pipeline timing summary."""

    total_ms: float
    steps: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class RetrievalDebugInfo:
    """Optional diagnostic information for debugging and observability."""

    query_tokens: tuple[str, ...]
    technical_terms: tuple[str, ...]
    dense_candidate_count: int = 0
    keyword_candidate_count: int = 0
    trace_steps: tuple[RetrievalTraceStep, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(slots=True)
class RetrievalResponse:
    """Final response returned by the retrieval service."""

    original_query: str
    normalized_query: str
    retrieval_mode: str
    top_k_results: int
    results: tuple[RetrievedChunk, ...]
    timings: RetrievalTiming
    domain: str | None = None
    domain_confidence: float | None = None
    domain_reason: str | None = None
    domain_mode: str | None = None
    domain_filter_applied: bool = False
    debug: RetrievalDebugInfo | None = None
