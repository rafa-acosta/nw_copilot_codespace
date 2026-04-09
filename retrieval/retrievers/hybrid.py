"""Hybrid dense plus keyword retrieval."""

from __future__ import annotations

from retrieval.config import RetrievalConfig
from retrieval.models import MetadataFilterSpec, ProcessedQuery, ScoredChunkCandidate
from retrieval.retrievers.base import Retriever
from retrieval.retrievers.keyword import KeywordRetriever
from retrieval.retrievers.vector import VectorRetriever
from retrieval.utils import min_max_normalize, reciprocal_rank_score, weighted_sum


class HybridRetriever(Retriever):
    """Combines dense and keyword retrieval with source-aware fusion."""

    def __init__(
        self,
        vector_retriever: VectorRetriever,
        keyword_retriever: KeywordRetriever,
        config: RetrievalConfig,
    ) -> None:
        self.vector_retriever = vector_retriever
        self.keyword_retriever = keyword_retriever
        self.config = config

    def retrieve(
        self,
        query: ProcessedQuery,
        *,
        top_k: int,
        filters: MetadataFilterSpec | None = None,
        query_embedding: tuple[float, ...] | None = None,
        score_threshold: float | None = None,
    ) -> list[ScoredChunkCandidate]:
        if query_embedding is None:
            raise ValueError("HybridRetriever requires a query embedding")

        candidate_pool_size = max(top_k, top_k * self.config.hybrid.candidate_pool_multiplier)
        dense_candidates = self.vector_retriever.retrieve(
            query,
            top_k=candidate_pool_size,
            filters=filters,
            query_embedding=query_embedding,
            score_threshold=score_threshold,
        )
        keyword_candidates = self.keyword_retriever.retrieve(
            query,
            top_k=candidate_pool_size,
            filters=filters,
            score_threshold=score_threshold,
        )

        dense_by_id = {candidate.chunk_id: candidate for candidate in dense_candidates}
        keyword_by_id = {candidate.chunk_id: candidate for candidate in keyword_candidates}
        dense_norm = min_max_normalize({chunk_id: candidate.score for chunk_id, candidate in dense_by_id.items()})
        keyword_norm = min_max_normalize(
            {chunk_id: candidate.score for chunk_id, candidate in keyword_by_id.items()}
        )

        dense_ranks = {candidate.chunk_id: index + 1 for index, candidate in enumerate(dense_candidates)}
        keyword_ranks = {candidate.chunk_id: index + 1 for index, candidate in enumerate(keyword_candidates)}

        merged: list[ScoredChunkCandidate] = []
        for chunk_id in set(dense_by_id).union(keyword_by_id):
            reference = dense_by_id.get(chunk_id) or keyword_by_id.get(chunk_id)
            if reference is None:
                continue

            record = reference.record
            profile = self.config.profile_for(record.metadata.source_type)
            dense_weight = self.config.hybrid.dense_weight * profile.dense_weight
            keyword_weight = self.config.hybrid.keyword_weight * profile.keyword_weight
            weight_sum = max(dense_weight + keyword_weight, 1e-9)

            if self.config.hybrid.fusion_strategy == "rrf":
                dense_component = reciprocal_rank_score(
                    dense_ranks.get(chunk_id),
                    self.config.hybrid.reciprocal_rank_constant,
                )
                keyword_component = reciprocal_rank_score(
                    keyword_ranks.get(chunk_id),
                    self.config.hybrid.reciprocal_rank_constant,
                )
                fused_score = weighted_sum(
                    dense_component,
                    keyword_component,
                    dense_weight,
                    keyword_weight,
                ) / weight_sum
            else:
                fused_score = weighted_sum(
                    dense_norm.get(chunk_id, 0.0),
                    keyword_norm.get(chunk_id, 0.0),
                    dense_weight,
                    keyword_weight,
                ) / weight_sum

            merged.append(
                ScoredChunkCandidate(
                    record=record,
                    score=fused_score,
                    dense_score=dense_by_id.get(chunk_id).score if chunk_id in dense_by_id else None,
                    keyword_score=keyword_by_id.get(chunk_id).score if chunk_id in keyword_by_id else None,
                    fused_score=fused_score,
                    matched_terms=keyword_by_id.get(chunk_id).matched_terms if chunk_id in keyword_by_id else (),
                )
            )

        merged.sort(key=lambda candidate: candidate.score, reverse=True)
        return merged[:top_k]
