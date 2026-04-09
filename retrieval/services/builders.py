"""Integration helpers for constructing retrieval services."""

from __future__ import annotations

from typing import Mapping, Sequence

from retrieval.config import RetrievalConfig
from retrieval.embedders import QueryEmbedder
from retrieval.models import StoredChunk
from retrieval.models.records import JsonValue
from retrieval.retrievers import HybridRetriever, InMemoryVectorStore, KeywordRetriever, VectorRetriever
from retrieval.rerankers import HeuristicReranker
from retrieval.services.retrieval_service import RetrievalService


def build_stored_chunks(
    chunks: Sequence[object],
    embeddings: Sequence[Sequence[float]],
    *,
    chunk_tags: Sequence[Sequence[str]] | None = None,
    custom_metadata: Sequence[Mapping[str, JsonValue]] | None = None,
    column_names: Sequence[Sequence[str]] | None = None,
) -> list[StoredChunk]:
    """Convert processed chunks plus embeddings into retrieval records."""

    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")

    tags_collection = chunk_tags or [()] * len(chunks)
    metadata_collection = custom_metadata or [{}] * len(chunks)
    columns_collection = column_names or [()] * len(chunks)

    return [
        StoredChunk.from_processing_chunk(
            chunk,
            embedding,
            tags=tags_collection[index],
            custom_metadata=metadata_collection[index],
            column_names=columns_collection[index],
        )
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]


def build_retrieval_service(
    records: Sequence[StoredChunk],
    *,
    query_embedder: QueryEmbedder,
    config: RetrievalConfig | None = None,
) -> RetrievalService:
    """Build a full retrieval service around local stored chunks."""

    resolved_config = config or RetrievalConfig()
    vector_store = InMemoryVectorStore(records)
    vector_retriever = VectorRetriever(vector_store, resolved_config.vector)
    keyword_retriever = (
        KeywordRetriever(vector_store, resolved_config.keyword)
        if resolved_config.keyword.enabled
        else None
    )
    hybrid_retriever = (
        HybridRetriever(vector_retriever, keyword_retriever, resolved_config)
        if resolved_config.hybrid.enabled and keyword_retriever is not None
        else None
    )
    reranker = HeuristicReranker(resolved_config) if resolved_config.reranker.enabled else None
    return RetrievalService(
        query_embedder=query_embedder,
        vector_retriever=vector_retriever,
        keyword_retriever=keyword_retriever,
        hybrid_retriever=hybrid_retriever,
        reranker=reranker,
        config=resolved_config,
    )
