"""Retrieval orchestration service."""

from __future__ import annotations

from typing import Sequence

from retrieval.config import RetrievalConfig
from retrieval.embedders import QueryEmbedder
from retrieval.models import (
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
                details={"candidate_count": len(candidates)},
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
                notes=tuple(notes),
            )

        return RetrievalResponse(
            original_query=request.query,
            normalized_query=processed_query.normalized_query,
            retrieval_mode=mode.value,
            top_k_results=len(results),
            results=results,
            timings=RetrievalTiming(total_ms=timer.total_ms, steps=dict(timer.steps)),
            debug=debug,
        )

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
