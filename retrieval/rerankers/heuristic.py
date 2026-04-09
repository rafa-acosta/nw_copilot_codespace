"""Heuristic reranker optimized for technical local RAG corpora."""

from __future__ import annotations

from typing import Sequence

from retrieval.config import RetrievalConfig
from retrieval.models import ProcessedQuery, ScoredChunkCandidate
from retrieval.rerankers.base import Reranker
from retrieval.utils import contains_term


class HeuristicReranker(Reranker):
    """Applies query-aware boosts using exact matches and metadata signals."""

    def __init__(self, config: RetrievalConfig) -> None:
        self.config = config

    def rerank(
        self,
        query: ProcessedQuery,
        candidates: Sequence[ScoredChunkCandidate],
        *,
        top_k: int,
    ) -> list[ScoredChunkCandidate]:
        reranked: list[ScoredChunkCandidate] = []
        for candidate in candidates:
            base_score = candidate.fused_score if candidate.fused_score is not None else candidate.score
            score = base_score
            boosts: list[str] = list(candidate.applied_boosts)
            metadata = candidate.record.metadata
            search_text = candidate.record.search_text or candidate.record.text
            metadata_blob = " ".join(metadata.searchable_values())
            profile = self.config.profile_for(metadata.source_type)

            exact_phrases = list(query.quoted_phrases)
            if len(query.normalized_query.split()) > 1:
                exact_phrases.append(query.normalized_query)
            exact_hits = sum(1 for phrase in exact_phrases if contains_term(search_text, phrase))
            if exact_hits:
                score += exact_hits * self.config.reranker.exact_phrase_boost * (1.0 + profile.exact_match_weight)
                boosts.append("exact_phrase")

            technical_hits = sum(1 for term in query.technical_terms if contains_term(search_text, term))
            if technical_hits:
                score += technical_hits * self.config.reranker.technical_term_boost * (1.0 + profile.exact_match_weight)
                boosts.append("technical_match")

            metadata_hits = sum(1 for term in query.tokens if contains_term(metadata_blob, term))
            metadata_hits += sum(1 for term in query.technical_terms if contains_term(metadata_blob, term))
            if metadata_hits:
                score += metadata_hits * self.config.reranker.metadata_match_boost * (1.0 + profile.metadata_weight)
                boosts.append("metadata_match")

            if metadata.source_type in query.hints.preferred_source_types:
                score += self.config.reranker.source_hint_boost
                boosts.append("source_hint")

            score, source_boosts = self._source_specific_boosts(query, candidate, score)
            if source_boosts:
                boosts.extend(source_boosts)

            reranked.append(
                ScoredChunkCandidate(
                    record=candidate.record,
                    score=score,
                    dense_score=candidate.dense_score,
                    keyword_score=candidate.keyword_score,
                    fused_score=candidate.fused_score,
                    rerank_score=score,
                    matched_terms=candidate.matched_terms,
                    applied_boosts=tuple(boosts),
                )
            )

        reranked.sort(key=lambda candidate: candidate.score, reverse=True)
        return reranked[:top_k]

    def _source_specific_boosts(
        self,
        query: ProcessedQuery,
        candidate: ScoredChunkCandidate,
        score: float,
    ) -> tuple[float, list[str]]:
        metadata = candidate.record.metadata
        boosts: list[str] = []

        if metadata.source_type == "pdf" and metadata.page_number in query.hints.page_numbers:
            score += self.config.reranker.page_match_boost
            boosts.append("page_match")

        if metadata.source_type in {"docx", "web", "text", "text_file"}:
            section = metadata.section or " ".join(metadata.structural_path)
            if any(contains_term(section, term) for term in query.hints.section_terms):
                score += self.config.reranker.section_match_boost
                boosts.append("section_match")

        if metadata.source_type == "excel":
            if metadata.sheet_name and any(contains_term(metadata.sheet_name, sheet) for sheet in query.hints.sheet_names):
                score += self.config.reranker.sheet_match_boost
                boosts.append("sheet_match")
            column_hits = sum(1 for token in query.tokens if any(contains_term(column, token) for column in metadata.column_names))
            if column_hits:
                score += column_hits * self.config.reranker.column_match_boost
                boosts.append("column_match")

        if metadata.source_type == "json" and metadata.json_key_path:
            if any(
                contains_term(metadata.json_key_path, json_path) or contains_term(json_path, metadata.json_key_path)
                for json_path in query.hints.json_paths
            ):
                score += self.config.reranker.json_path_boost
                boosts.append("json_path_match")

        if metadata.source_type in {"cisco", "cisco_config"}:
            cisco_targets = " ".join(part for part in (metadata.cisco_feature, metadata.cisco_section, candidate.record.text) if part)
            cisco_hits = sum(1 for term in query.hints.cisco_terms or query.technical_terms if contains_term(cisco_targets, term))
            if cisco_hits:
                score += cisco_hits * self.config.reranker.cisco_command_boost
                boosts.append("cisco_match")

        return score, boosts
