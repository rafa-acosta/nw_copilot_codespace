"""Chroma-backed vector store implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import chromadb
except ImportError:
    chromadb = None

from retrieval.filters import MetadataFilter
from retrieval.models import ChunkMetadata, MetadataFilterSpec, ScoredChunkCandidate, StoredChunk, infer_embedding_dimension

from .store import VectorStore


class ChromaVectorStore(VectorStore):
    """Persistent local vector store backed by Chroma."""

    def __init__(
        self,
        *,
        persist_directory: str | Path,
        collection_name: str,
        records: Sequence[StoredChunk] | None = None,
        metadata_filter: MetadataFilter | None = None,
        reset_collection: bool = False,
        batch_size: int = 100,
    ) -> None:
        if chromadb is None:
            raise ImportError("chromadb is required for ChromaVectorStore. Install with: pip install chromadb")

        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.metadata_filter = metadata_filter or MetadataFilter()
        self.batch_size = max(1, batch_size)
        self.client = chromadb.PersistentClient(path=str(self.persist_directory))
        self.collection = self._open_collection(reset_collection=reset_collection)

        if records is not None:
            self.replace_records(records)

        self._embedding_dimension = infer_embedding_dimension(records) or self._infer_embedding_dimension() or 0

    @property
    def embedding_dimension(self) -> int:
        return self._embedding_dimension

    def replace_records(self, records: Sequence[StoredChunk]) -> None:
        self.collection = self._open_collection(reset_collection=True)
        if not records:
            return

        for batch in self._batched(records, self.batch_size):
            self.collection.add(
                ids=[self._require_chunk_id(record) for record in batch],
                embeddings=[list(record.embedding) for record in batch],
                documents=[record.text for record in batch],
                metadatas=[self._serialize_metadata(record.metadata) for record in batch],
            )

        self._embedding_dimension = len(records[0].embedding)

    def search(
        self,
        query_embedding: Sequence[float],
        *,
        top_k: int,
        filters: MetadataFilterSpec | None = None,
    ) -> list[ScoredChunkCandidate]:
        if self.collection.count() == 0:
            return []

        if len(query_embedding) != self._embedding_dimension:
            raise ValueError(
                f"Query embedding dimension mismatch: expected={self._embedding_dimension} actual={len(query_embedding)}"
            )

        where = self._to_chroma_where(filters)
        requires_post_filter = self._requires_post_filter(filters)
        requested_results = top_k if not requires_post_filter else min(self.collection.count(), max(top_k * 3, top_k))
        if requested_results <= 0:
            return []

        results = self.collection.query(
            query_embeddings=[list(float(value) for value in query_embedding)],
            n_results=requested_results,
            where=where,
            include=["documents", "metadatas", "distances", "embeddings"],
        )

        candidates: list[ScoredChunkCandidate] = []
        ids = self._coerce_result_array(results.get("ids"))
        documents = self._coerce_result_array(results.get("documents"))
        embeddings = self._coerce_result_array(results.get("embeddings"))
        metadatas = self._coerce_result_array(results.get("metadatas"))
        distances = self._coerce_result_array(results.get("distances"))
        ids = ids[0] if ids else []
        documents = documents[0] if documents else []
        embeddings = embeddings[0] if embeddings else []
        metadatas = metadatas[0] if metadatas else []
        distances = distances[0] if distances else []

        for chunk_id, document, embedding, metadata, distance in zip(ids, documents, embeddings, metadatas, distances):
            record = self._to_stored_chunk(chunk_id, document, embedding, metadata)
            if requires_post_filter and not self.metadata_filter.matches(record.metadata, filters):
                continue
            score = 1.0 - float(distance or 0.0)
            candidates.append(
                ScoredChunkCandidate(
                    record=record,
                    score=score,
                    dense_score=score,
                )
            )

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        return candidates[:top_k]

    def get_chunks(self, chunk_ids: Sequence[str]) -> list[StoredChunk]:
        if not chunk_ids:
            return []

        results = self.collection.get(
            ids=list(chunk_ids),
            include=["documents", "metadatas", "embeddings"],
        )
        records_by_id = {
            chunk_id: self._to_stored_chunk(chunk_id, document, embedding, metadata)
            for chunk_id, document, embedding, metadata in zip(
                self._coerce_result_array(results.get("ids")),
                self._coerce_result_array(results.get("documents")),
                self._coerce_result_array(results.get("embeddings")),
                self._coerce_result_array(results.get("metadatas")),
            )
        }
        return [records_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in records_by_id]

    def iter_chunks(self, filters: MetadataFilterSpec | None = None) -> Iterable[StoredChunk]:
        where = self._to_chroma_where(filters)
        requires_post_filter = self._requires_post_filter(filters)
        offset = 0

        while True:
            results = self.collection.get(
                where=where,
                limit=self.batch_size,
                offset=offset,
                include=["documents", "metadatas", "embeddings"],
            )
            ids = self._coerce_result_array(results.get("ids"))
            if not ids:
                break

            documents = self._coerce_result_array(results.get("documents"))
            embeddings = self._coerce_result_array(results.get("embeddings"))
            metadatas = self._coerce_result_array(results.get("metadatas"))

            for chunk_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas):
                record = self._to_stored_chunk(chunk_id, document, embedding, metadata)
                if requires_post_filter and not self.metadata_filter.matches(record.metadata, filters):
                    continue
                yield record

            offset += len(ids)

    def peek_records(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        include_embeddings: bool = False,
    ) -> dict[str, Any]:
        include = ["documents", "metadatas"]
        if include_embeddings:
            include.append("embeddings")

        results = self.collection.get(
            limit=max(1, limit),
            offset=max(0, offset),
            include=include,
        )

        ids = self._coerce_result_array(results.get("ids"))
        documents = self._coerce_result_array(results.get("documents"))
        metadatas = self._coerce_result_array(results.get("metadatas"))
        embeddings = self._coerce_result_array(results.get("embeddings"))
        records = []

        for index, chunk_id in enumerate(ids):
            embedding = embeddings[index] if include_embeddings and index < len(embeddings) else None
            records.append(
                {
                    "chunk_id": chunk_id,
                    "document": documents[index] if index < len(documents) else None,
                    "metadata": self._deserialize_metadata_dict(metadatas[index] if index < len(metadatas) else None),
                    "embedding_dimension": len(embedding) if embedding is not None else self._embedding_dimension,
                    "embedding_preview": list(embedding[:8]) if embedding is not None else [],
                    "embedding": list(embedding) if embedding is not None else None,
                }
            )

        return {
            "path": str(self.persist_directory),
            "collection_name": self.collection_name,
            "total": self.collection.count(),
            "records": records,
        }

    @classmethod
    def clear_collection(cls, persist_directory: str | Path, collection_name: str) -> None:
        if chromadb is None:
            return

        client = chromadb.PersistentClient(path=str(Path(persist_directory)))
        try:
            client.delete_collection(collection_name)
        except Exception:
            return

    def _open_collection(self, *, reset_collection: bool) -> Any:
        if reset_collection:
            try:
                self.client.delete_collection(self.collection_name)
            except Exception:
                pass

        try:
            return self.client.get_or_create_collection(
                name=self.collection_name,
                configuration={"hnsw": {"space": "cosine"}},
            )
        except TypeError:
            return self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

    def _infer_embedding_dimension(self) -> int | None:
        preview = self.collection.get(limit=1, include=["embeddings"])
        embeddings = self._coerce_result_array(preview.get("embeddings"))
        if not embeddings:
            return None
        return len(embeddings[0])

    @staticmethod
    def _batched(records: Sequence[StoredChunk], batch_size: int = 100) -> Iterable[Sequence[StoredChunk]]:
        for start in range(0, len(records), batch_size):
            yield records[start:start + batch_size]

    @staticmethod
    def _require_chunk_id(record: StoredChunk) -> str:
        chunk_id = record.metadata.chunk_id
        if chunk_id is None:
            raise ValueError("StoredChunk.metadata.chunk_id must be set")
        return chunk_id

    def _to_stored_chunk(
        self,
        chunk_id: str,
        document: str | None,
        embedding: Sequence[float] | None,
        metadata: Mapping[str, Any] | None,
    ) -> StoredChunk:
        if embedding is None:
            raise ValueError(f"Chroma record {chunk_id} did not include an embedding")
        return StoredChunk(
            text=document or "",
            embedding=tuple(float(value) for value in embedding),
            metadata=self._deserialize_metadata(chunk_id, metadata),
        )

    @staticmethod
    def _serialize_metadata(metadata: ChunkMetadata) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_id": metadata.document_id,
            "source_type": metadata.source_type,
            "chunk_id": metadata.chunk_id,
        }

        for field_name in (
            "file_path",
            "filename",
            "page_number",
            "section",
            "sheet_name",
            "row_start",
            "row_end",
            "json_key_path",
            "cisco_feature",
            "cisco_section",
            "domain",
            "domain_confidence",
            "domain_reason",
        ):
            value = getattr(metadata, field_name)
            if value is not None:
                payload[field_name] = value

        for field_name in ("column_names", "tags", "structural_path"):
            values = tuple(getattr(metadata, field_name) or ())
            if values:
                payload[field_name] = [str(value) for value in values]

        if metadata.custom:
            payload["_custom_json"] = json.dumps(metadata.custom, ensure_ascii=True, sort_keys=True)

        return payload

    @staticmethod
    def _deserialize_metadata(chunk_id: str, metadata: Mapping[str, Any] | None) -> ChunkMetadata:
        payload = ChromaVectorStore._deserialize_metadata_dict(metadata)
        return ChunkMetadata(
            document_id=str(payload.get("document_id") or ""),
            source_type=str(payload.get("source_type") or ""),
            file_path=ChromaVectorStore._optional_str(payload.get("file_path")),
            filename=ChromaVectorStore._optional_str(payload.get("filename")),
            chunk_id=ChromaVectorStore._optional_str(payload.get("chunk_id")) or chunk_id,
            page_number=ChromaVectorStore._optional_int(payload.get("page_number")),
            section=ChromaVectorStore._optional_str(payload.get("section")),
            sheet_name=ChromaVectorStore._optional_str(payload.get("sheet_name")),
            row_start=ChromaVectorStore._optional_int(payload.get("row_start")),
            row_end=ChromaVectorStore._optional_int(payload.get("row_end")),
            column_names=tuple(str(value) for value in payload.get("column_names", []) or ()),
            json_key_path=ChromaVectorStore._optional_str(payload.get("json_key_path")),
            cisco_feature=ChromaVectorStore._optional_str(payload.get("cisco_feature")),
            cisco_section=ChromaVectorStore._optional_str(payload.get("cisco_section")),
            domain=ChromaVectorStore._optional_str(payload.get("domain")),
            domain_confidence=ChromaVectorStore._optional_float(payload.get("domain_confidence")),
            domain_reason=ChromaVectorStore._optional_str(payload.get("domain_reason")),
            tags=tuple(str(value) for value in payload.get("tags", []) or ()),
            structural_path=tuple(str(value) for value in payload.get("structural_path", []) or ()),
            custom=dict(payload.get("custom", {})),
        )

    @staticmethod
    def _deserialize_metadata_dict(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
        payload = dict(metadata or {})
        custom_json = payload.pop("_custom_json", None)
        if isinstance(custom_json, str) and custom_json.strip():
            try:
                payload["custom"] = json.loads(custom_json)
            except json.JSONDecodeError:
                payload["custom"] = {"raw": custom_json}
        else:
            payload["custom"] = {}
        return payload

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value)
        return text if text else None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _coerce_result_array(value: Any) -> list[Any]:
        if value is None:
            return []
        if hasattr(value, "tolist"):
            return value.tolist()
        return list(value)

    @staticmethod
    def _requires_post_filter(filters: MetadataFilterSpec | None) -> bool:
        if filters is None:
            return False
        return bool(filters.contains)

    @staticmethod
    def _to_chroma_where(filters: MetadataFilterSpec | None) -> dict[str, Any] | None:
        if filters is None or filters.is_empty():
            return None

        clauses: list[dict[str, Any]] = []

        for field_name, expected in filters.equals.items():
            clauses.append({field_name: expected})

        for field_name, expected_values in filters.any_of.items():
            values = list(expected_values)
            if values:
                clauses.append({field_name: {"$in": values}})

        for field_name, numeric_range in filters.numeric_ranges.items():
            if numeric_range.minimum is not None:
                operator = "$gte" if numeric_range.include_minimum else "$gt"
                clauses.append({field_name: {operator: numeric_range.minimum}})
            if numeric_range.maximum is not None:
                operator = "$lte" if numeric_range.include_maximum else "$lt"
                clauses.append({field_name: {operator: numeric_range.maximum}})

        if filters.tags_any:
            tag_clauses = [{"tags": {"$contains": tag}} for tag in filters.tags_any]
            if len(tag_clauses) == 1:
                clauses.append(tag_clauses[0])
            else:
                clauses.append({"$or": tag_clauses})

        for tag in filters.tags_all:
            clauses.append({"tags": {"$contains": tag}})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}
