"""Keyword and exact-match retrieval for technical corpora."""

from __future__ import annotations

from collections import Counter, defaultdict
import math

from retrieval.config import KeywordRetrieverConfig
from retrieval.filters import MetadataFilter
from retrieval.models import MetadataFilterSpec, ProcessedQuery, ScoredChunkCandidate, StoredChunk
from retrieval.retrievers.base import Retriever
from retrieval.retrievers.store import VectorStore
from retrieval.utils import contains_term, normalize_for_lookup, tokenize_preserving_technical, unique_preserve_order


class KeywordRetriever(Retriever):
    """Keyword retrieval with exact-phrase boosts for structured documents."""

    def __init__(
        self,
        vector_store: VectorStore,
        config: KeywordRetrieverConfig | None = None,
        *,
        metadata_filter: MetadataFilter | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.config = config or KeywordRetrieverConfig()
        self.metadata_filter = metadata_filter or MetadataFilter()
        self._record_cache: dict[str, StoredChunk] = {}
        self._search_blobs: dict[str, str] = {}
        self._metadata_blobs: dict[str, str] = {}
        self._term_postings: dict[str, dict[str, int]] = defaultdict(dict)
        self._document_lengths: dict[str, int] = {}
        self._document_count = 0
        self._build_index()

    def refresh(self) -> None:
        self._record_cache.clear()
        self._search_blobs.clear()
        self._metadata_blobs.clear()
        self._term_postings.clear()
        self._document_lengths.clear()
        self._document_count = 0
        self._build_index()

    def retrieve(
        self,
        query: ProcessedQuery,
        *,
        top_k: int,
        filters: MetadataFilterSpec | None = None,
        query_embedding: object | None = None,
        score_threshold: float | None = None,
    ) -> list[ScoredChunkCandidate]:
        del query_embedding
        query_terms = self._query_terms(query)
        if not query_terms and not query.quoted_phrases:
            return []

        scores: dict[str, float] = defaultdict(float)
        matched_terms: dict[str, set[str]] = defaultdict(set)

        for term in query_terms:
            postings = self._term_postings.get(term, {})
            if not postings:
                continue
            idf = math.log((self._document_count + 1) / (len(postings) + 1)) + 1.0
            for chunk_id, term_frequency in postings.items():
                tf_weight = 1.0 + math.log(term_frequency)
                scores[chunk_id] += tf_weight * idf
                matched_terms[chunk_id].add(term)

        for chunk_id in list(scores.keys()):
            blob = self._search_blobs[chunk_id]
            metadata_blob = self._metadata_blobs[chunk_id]
            scores[chunk_id] += self._phrase_boost(query, blob)
            scores[chunk_id] += self._technical_boost(query, blob)
            scores[chunk_id] += self._metadata_boost(query, metadata_blob)

        candidates: list[ScoredChunkCandidate] = []
        threshold = score_threshold if score_threshold is not None else None
        for chunk_id, score in scores.items():
            record = self._record_cache[chunk_id]
            if not self.metadata_filter.matches(record.metadata, filters):
                continue
            if threshold is not None and score < threshold:
                continue
            candidates.append(
                ScoredChunkCandidate(
                    record=record,
                    score=score,
                    keyword_score=score,
                    matched_terms=tuple(sorted(matched_terms.get(chunk_id, set()))),
                )
            )

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        return candidates[:top_k]

    def _build_index(self) -> None:
        for record in self.vector_store.iter_chunks():
            chunk_id = self._require_chunk_id(record)
            self._record_cache[chunk_id] = record
            search_blob = normalize_for_lookup(record.search_text or record.text)
            metadata_blob = normalize_for_lookup(" ".join(record.metadata.searchable_values()))
            self._search_blobs[chunk_id] = search_blob
            self._metadata_blobs[chunk_id] = metadata_blob
            terms = Counter(tokenize_preserving_technical(search_blob))
            self._document_lengths[chunk_id] = sum(terms.values())
            for term, frequency in terms.items():
                self._term_postings[term][chunk_id] = frequency
            self._document_count += 1

    def _query_terms(self, query: ProcessedQuery) -> tuple[str, ...]:
        terms = list(query.tokens)
        terms.extend(normalize_for_lookup(term) for term in query.technical_terms)
        terms.extend(normalize_for_lookup(expansion) for expansion in query.expansions)
        return unique_preserve_order(
            [term for term in terms if len(term) >= self.config.minimum_token_length]
        )

    def _phrase_boost(self, query: ProcessedQuery, blob: str) -> float:
        phrases = list(query.quoted_phrases)
        if len(query.normalized_query.split()) > 1:
            phrases.append(query.normalized_query)
        hits = sum(1 for phrase in unique_preserve_order(phrases) if contains_term(blob, phrase))
        return hits * self.config.exact_phrase_boost

    def _technical_boost(self, query: ProcessedQuery, blob: str) -> float:
        hits = sum(1 for term in query.technical_terms if contains_term(blob, term))
        return hits * self.config.technical_term_boost

    def _metadata_boost(self, query: ProcessedQuery, metadata_blob: str) -> float:
        metadata_terms = sum(1 for term in query.tokens if contains_term(metadata_blob, term))
        metadata_terms += sum(1 for term in query.technical_terms if contains_term(metadata_blob, term))
        return metadata_terms * self.config.metadata_field_boost

    @staticmethod
    def _require_chunk_id(record: StoredChunk) -> str:
        chunk_id = record.metadata.chunk_id
        if chunk_id is None:
            raise ValueError("StoredChunk.metadata.chunk_id must be set")
        return chunk_id
