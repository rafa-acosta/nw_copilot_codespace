"""Retrieval orchestration service."""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from retrieval.config import RetrievalConfig
from retrieval.embedders import QueryEmbedder
from retrieval.models import (
    ProcessedQuery,
    RetrievalDebugInfo,
    RetrievalMode,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalTiming,
    RetrievalTraceStep,
    RetrievedChunk,
    ScoredChunkCandidate,
)
from retrieval.query_processing import QueryProcessor, TechnicalQueryProcessor
from retrieval.rerankers import HeuristicReranker, Reranker
from retrieval.retrievers import HybridRetriever, KeywordRetriever, VectorRetriever
from retrieval.utils import StageTimer, configure_logger


class RetrievalService:
    """Coordinates query processing, retrieval, reranking, and response formatting."""

    def __init__(
        self,
        *,
        query_embedder: QueryEmbedder | None,
        query_processor: QueryProcessor | None = None,
        vector_retriever: VectorRetriever | None = None,
        keyword_retriever: KeywordRetriever | None = None,
        hybrid_retriever: HybridRetriever | None = None,
        reranker: Reranker | None = None,
        config: RetrievalConfig | None = None,
    ) -> None:
        self.config = config or RetrievalConfig()
        self.query_processor = query_processor or TechnicalQueryProcessor(self.config.query_processing)
        self.query_embedder = query_embedder
        self.vector_retriever = vector_retriever
        self.keyword_retriever = keyword_retriever
        self.hybrid_retriever = hybrid_retriever
        if reranker is not None:
            self.reranker = reranker
        elif self.config.reranker.enabled:
            self.reranker = HeuristicReranker(self.config)
        else:
            self.reranker = None
        self.logger = configure_logger(
            self.config.observability.logger_name,
            self.config.observability.log_level,
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        timer = StageTimer()
        trace_steps: list[RetrievalTraceStep] = []
        debug_enabled = request.debug if request.debug is not None else self.config.observability.debug
        notes: list[str] = []
        if request.domain:
            notes.append(
                f"Domain route={request.domain} mode={request.domain_mode or 'automatic'} "
                f"confidence={request.domain_confidence or 0.0:.2f} filter_applied={request.domain_filter_applied}"
            )

        with timer.measure("query_processing"):
            processed_query = self.query_processor.process(request.query)
        trace_steps.append(
            RetrievalTraceStep(
                name="query_processing",
                duration_ms=timer.steps["query_processing"],
                details={
                    "token_count": len(processed_query.tokens),
                    "technical_term_count": len(processed_query.technical_terms),
                },
            )
        )

        mode = request.mode or RetrievalMode(self.config.retrieval_mode)
        top_k = request.top_k or self.config.vector.top_k

        query_embedding: tuple[float, ...] | None = None
        if mode in {RetrievalMode.DENSE, RetrievalMode.HYBRID}:
            if self.query_embedder is None:
                raise ValueError(f"{mode.value} retrieval requires a query embedder")
            with timer.measure("query_embedding"):
                query_embedding = self.query_embedder.embed(processed_query)
            trace_steps.append(
                RetrievalTraceStep(
                    name="query_embedding",
                    duration_ms=timer.steps["query_embedding"],
                    details={"embedding_dimension": len(query_embedding)},
                )
            )

        self.logger.info(
            "Retrieving query mode=%s top_k=%s filters=%s",
            mode.value,
            top_k,
            bool(request.filters),
        )

        with timer.measure("candidate_retrieval"):
            if self.config.multi_query.enabled and processed_query.variants:
                candidates = self._retrieve_multi_query_candidates(
                    processed_query,
                    mode=mode,
                    top_k=top_k,
                    query_embedding=query_embedding,
                    request=request,
                )
            else:
                candidates = self._retrieve_candidates(
                    processed_query,
                    mode=mode,
                    top_k=top_k,
                    query_embedding=query_embedding,
                    request=request,
                )
        trace_steps.append(
            RetrievalTraceStep(
                name="candidate_retrieval",
                duration_ms=timer.steps["candidate_retrieval"],
                details={
                    "candidate_count": len(candidates),
                    "query_variant_count": 1 + len(processed_query.variants)
                    if self.config.multi_query.enabled
                    else 1,
                },
            )
        )

        if self.reranker is not None and candidates:
            with timer.measure("reranking"):
                candidates = self.reranker.rerank(processed_query, candidates, top_k=top_k)
            trace_steps.append(
                RetrievalTraceStep(
                    name="reranking",
                    duration_ms=timer.steps["reranking"],
                    details={"reranked_count": len(candidates)},
                )
            )

        results = tuple(self._to_response_item(candidate) for candidate in candidates[:top_k])

        if mode == RetrievalMode.HYBRID and self.hybrid_retriever is None:
            notes.append("Hybrid mode requested but hybrid retriever was not configured.")
        if mode == RetrievalMode.KEYWORD and self.keyword_retriever is None:
            notes.append("Keyword mode requested but keyword retriever was not configured.")

        debug = None
        if debug_enabled:
            dense_count = sum(1 for candidate in candidates if candidate.dense_score is not None)
            keyword_count = sum(1 for candidate in candidates if candidate.keyword_score is not None)
            debug = RetrievalDebugInfo(
                query_tokens=processed_query.tokens,
                technical_terms=processed_query.technical_terms,
                dense_candidate_count=dense_count,
                keyword_candidate_count=keyword_count,
                trace_steps=tuple(trace_steps),
                notes=tuple((*notes, *self._multi_query_notes(processed_query))),
            )

        return RetrievalResponse(
            original_query=request.query,
            normalized_query=processed_query.normalized_query,
            retrieval_mode=mode.value,
            top_k_results=len(results),
            results=results,
            timings=RetrievalTiming(total_ms=timer.total_ms, steps=dict(timer.steps)),
            domain=request.domain,
            domain_confidence=request.domain_confidence,
            domain_reason=request.domain_reason,
            domain_mode=request.domain_mode,
            domain_filter_applied=request.domain_filter_applied,
            debug=debug,
        )

    def _retrieve_multi_query_candidates(
        self,
        query: ProcessedQuery,
        *,
        mode: RetrievalMode,
        top_k: int,
        query_embedding: Sequence[float] | None,
        request: RetrievalRequest,
    ) -> list[ScoredChunkCandidate]:
        candidate_limit = max(
            top_k,
            top_k * self.config.multi_query.candidate_pool_multiplier,
            self.config.vector.candidate_pool_size,
        )
        query_plan = [(query, query_embedding, self.config.multi_query.original_query_weight)]

        variant_texts = query.variants[: max(self.config.multi_query.max_queries - 1, 0)]
        for variant_text in variant_texts:
            variant_query = self.query_processor.process(variant_text)
            variant_query = replace(variant_query, variants=())
            variant_embedding = None
            if mode in {RetrievalMode.DENSE, RetrievalMode.HYBRID}:
                if self.query_embedder is None:
                    raise ValueError(f"{mode.value} retrieval requires a query embedder")
                variant_embedding = self.query_embedder.embed(variant_query)
            query_plan.append((variant_query, variant_embedding, self.config.multi_query.variant_query_weight))

        candidate_groups: dict[str, list[tuple[ScoredChunkCandidate, float, int]]] = {}
        for planned_query, planned_embedding, query_weight in query_plan:
            retrieved = self._retrieve_candidates(
                planned_query,
                mode=mode,
                top_k=candidate_limit,
                query_embedding=planned_embedding,
                request=request,
            )
            for rank, candidate in enumerate(retrieved, start=1):
                candidate_groups.setdefault(candidate.chunk_id, []).append((candidate, query_weight, rank))

        merged: list[ScoredChunkCandidate] = []
        for candidate_hits in candidate_groups.values():
            reference = candidate_hits[0][0]
            weighted_scores = [candidate.score * weight for candidate, weight, _rank in candidate_hits]
            rank_bonus = sum((weight / rank) * 0.05 for _candidate, weight, rank in candidate_hits)
            matched_terms = sorted(
                {
                    term
                    for candidate, _weight, _rank in candidate_hits
                    for term in candidate.matched_terms
                }
            )
            applied_boosts = sorted(
                {
                    boost
                    for candidate, _weight, _rank in candidate_hits
                    for boost in candidate.applied_boosts
                }
            )
            merged.append(
                ScoredChunkCandidate(
                    record=reference.record,
                    score=max(weighted_scores) + rank_bonus,
                    dense_score=max(
                        (candidate.dense_score for candidate, _weight, _rank in candidate_hits if candidate.dense_score is not None),
                        default=None,
                    ),
                    keyword_score=max(
                        (candidate.keyword_score for candidate, _weight, _rank in candidate_hits if candidate.keyword_score is not None),
                        default=None,
                    ),
                    fused_score=max(
                        (candidate.fused_score for candidate, _weight, _rank in candidate_hits if candidate.fused_score is not None),
                        default=None,
                    ),
                    matched_terms=tuple(matched_terms),
                    applied_boosts=tuple(applied_boosts),
                )
            )

        merged.sort(key=lambda candidate: candidate.score, reverse=True)
        return merged[:candidate_limit]

    def _multi_query_notes(self, query: ProcessedQuery) -> tuple[str, ...]:
        if not self.config.multi_query.enabled or not query.variants:
            return ()
        used_variants = query.variants[: max(self.config.multi_query.max_queries - 1, 0)]
        return (f"Multi-query variants used: {', '.join(used_variants)}",) if used_variants else ()

    def _retrieve_candidates(
        self,
        query: ProcessedQuery,
        *,
        mode: RetrievalMode,
        top_k: int,
        query_embedding: Sequence[float] | None,
        request: RetrievalRequest,
    ) -> list[ScoredChunkCandidate]:
        if mode == RetrievalMode.DENSE:
            if self.vector_retriever is None:
                raise ValueError("Dense retrieval requested but vector retriever is not configured")
            return self.vector_retriever.retrieve(
                query,
                top_k=top_k,
                filters=request.filters,
                query_embedding=query_embedding,
                score_threshold=request.score_threshold,
            )

        if mode == RetrievalMode.KEYWORD:
            if self.keyword_retriever is None:
                raise ValueError("Keyword retrieval requested but keyword retriever is not configured")
            return self.keyword_retriever.retrieve(
                query,
                top_k=top_k,
                filters=request.filters,
                score_threshold=request.score_threshold,
            )

        if self.hybrid_retriever is None:
            if self.keyword_retriever is not None and self.vector_retriever is not None:
                self.hybrid_retriever = HybridRetriever(
                    self.vector_retriever,
                    self.keyword_retriever,
                    self.config,
                )
            else:
                raise ValueError("Hybrid retrieval requested but hybrid retriever is not configured")

        return self.hybrid_retriever.retrieve(
            query,
            top_k=top_k,
            filters=request.filters,
            query_embedding=query_embedding,
            score_threshold=request.score_threshold,
        )

    @staticmethod
    def _to_response_item(candidate: ScoredChunkCandidate) -> RetrievedChunk:
        metadata = candidate.record.metadata
        return RetrievedChunk(
            chunk_id=candidate.chunk_id,
            text=candidate.record.text,
            score=candidate.score,
            metadata=metadata.as_dict(),
            source_type=metadata.source_type,
            dense_score=candidate.dense_score,
            keyword_score=candidate.keyword_score,
            rerank_score=candidate.rerank_score,
            matched_terms=candidate.matched_terms,
            applied_boosts=candidate.applied_boosts,
        )
