"""Application services for the local copilot GUI."""

from __future__ import annotations

import base64
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import threading
from uuid import uuid4

from copilot_ui.answers import AnswerGenerator, GroundedAnswerGenerator
from copilot_ui.embeddings import HashingEmbeddingModel
from copilot_ui.loaders import load_document
from copilot_ui.models import (
    AppSnapshot,
    ChatMessage,
    IndexedDocument,
    IndexedDocumentSummary,
    UploadedFilePayload,
)
from rag_processing import CleanDocument, DocumentPipeline
from retrieval import MetadataFilterSpec, RetrievalConfig, RetrievalMode, RetrievalRequest
from retrieval.services import build_retrieval_service, build_stored_chunks
from retrieval.utils import extract_sheet_headers


@dataclass(slots=True)
class QueryOptions:
    """Query controls exposed to the frontend."""

    mode: str = RetrievalMode.HYBRID.value
    top_k: int = 4
    source_types: tuple[str, ...] = ()
    debug: bool = False


class CopilotApplicationService:
    """Owns document indexing, retrieval, and chat state for the GUI."""

    SUPPORTED_SOURCE_TYPES = (
        "text",
        "text_file",
        "pdf",
        "docx",
        "excel",
        "json",
        "cisco",
        "cisco_config",
    )

    def __init__(
        self,
        *,
        storage_dir: str | Path | None = None,
        retrieval_config: RetrievalConfig | None = None,
        embedding_model: HashingEmbeddingModel | None = None,
        answer_generator: AnswerGenerator | None = None,
    ) -> None:
        self.storage_dir = Path(storage_dir or "/tmp/nw_copilot_ui")
        self.upload_dir = self.storage_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        self.retrieval_config = retrieval_config or RetrievalConfig()
        self.embedding_model = embedding_model or HashingEmbeddingModel()
        self.answer_generator = answer_generator or GroundedAnswerGenerator()
        self.processing_pipeline = DocumentPipeline(max_size=900, overlap=120)

        self._lock = threading.RLock()
        self._documents: dict[str, IndexedDocument] = {}
        self._records = []
        self._messages: list[ChatMessage] = []
        self._retrieval_service = None

    def add_uploaded_files(self, payloads: list[UploadedFilePayload], *, clear_existing: bool = False) -> AppSnapshot:
        with self._lock:
            if clear_existing:
                self._clear_documents_locked()

            for payload in payloads:
                stored_path = self._persist_upload(payload)
                ingested = load_document(str(stored_path))
                clean_document = CleanDocument.from_ingested(ingested)
                chunks = self.processing_pipeline.run(clean_document)
                embeddings = self.embedding_model.embed_documents([chunk.content for chunk in chunks])
                column_names = [
                    extract_sheet_headers(chunk.content) if getattr(chunk.metadata, "sheet", None) else ()
                    for chunk in chunks
                ]
                stored_chunks = build_stored_chunks(chunks, embeddings, column_names=column_names)
                for record in stored_chunks:
                    record.metadata.filename = payload.name
                self._records.extend(stored_chunks)
                chunk_ids = tuple(record.metadata.chunk_id or "" for record in stored_chunks)
                summary = IndexedDocumentSummary(
                    document_id=clean_document.document_id,
                    filename=payload.name,
                    file_path=str(stored_path),
                    source_type=clean_document.source_type,
                    chunk_count=len(stored_chunks),
                )
                self._documents[summary.document_id] = IndexedDocument(
                    summary=summary,
                    chunk_ids=chunk_ids,
                    temp_path=str(stored_path),
                )

            self._rebuild_retrieval_service()
            return self.snapshot()

    def remove_document(self, document_id: str) -> AppSnapshot:
        with self._lock:
            indexed = self._documents.pop(document_id, None)
            if indexed is None:
                raise ValueError(f"Document not found: {document_id}")
            chunk_ids = set(indexed.chunk_ids)
            self._records = [record for record in self._records if (record.metadata.chunk_id or "") not in chunk_ids]
            temp_path = Path(indexed.temp_path)
            if temp_path.exists():
                temp_path.unlink()
            self._rebuild_retrieval_service()
            return self.snapshot()

    def clear_documents(self) -> AppSnapshot:
        with self._lock:
            self._clear_documents_locked()
            return self.snapshot()

    def clear_chat(self) -> AppSnapshot:
        with self._lock:
            self._messages.clear()
            return self.snapshot()

    def ask(self, message: str, options: QueryOptions | None = None) -> AppSnapshot:
        options = options or QueryOptions()
        user_message = ChatMessage(role="user", content=message.strip())

        with self._lock:
            self._messages.append(user_message)

            if self._retrieval_service is None:
                self._messages.append(
                    ChatMessage(
                        role="assistant",
                        content=(
                            "No documents are indexed yet.\n\n"
                            "Load one or more files from the sidebar so I can search them."
                        ),
                    )
                )
                return self.snapshot()

            filters = None
            if options.source_types:
                filters = MetadataFilterSpec(any_of={"source_type": options.source_types})

            retrieval_response = self._retrieval_service.retrieve(
                RetrievalRequest(
                    query=message,
                    top_k=options.top_k,
                    mode=RetrievalMode(options.mode),
                    filters=filters,
                    debug=options.debug,
                )
            )
            generated = self.answer_generator.generate(message, retrieval_response)
            assistant_message = ChatMessage(
                role="assistant",
                content=generated.content,
                citations=generated.citations,
                meta={
                    **generated.meta,
                    "source_counts": self._summarize_sources(retrieval_response),
                },
            )
            self._messages.append(assistant_message)
            return self.snapshot()

    def snapshot(self) -> AppSnapshot:
        with self._lock:
            documents = tuple(
                sorted(
                    (indexed.summary for indexed in self._documents.values()),
                    key=lambda summary: summary.added_at,
                )
            )
            messages = tuple(self._messages)
            return AppSnapshot(
                documents=documents,
                messages=messages,
                retrieval_ready=self._retrieval_service is not None,
                chunk_count=len(self._records),
                supported_types=self.SUPPORTED_SOURCE_TYPES,
            )

    def _persist_upload(self, payload: UploadedFilePayload) -> Path:
        safe_name = Path(payload.name).name or "upload.bin"
        target = self.upload_dir / f"{uuid4().hex}_{safe_name}"
        content = base64.b64decode(payload.content_base64.encode("utf-8"))
        target.write_bytes(content)
        return target

    def _rebuild_retrieval_service(self) -> None:
        if not self._records:
            self._retrieval_service = None
            return
        self._retrieval_service = build_retrieval_service(
            self._records,
            query_embedder=self.embedding_model.as_query_embedder(),
            config=self.retrieval_config,
        )

    def _clear_documents_locked(self) -> None:
        for indexed in self._documents.values():
            path = Path(indexed.temp_path)
            if path.exists():
                path.unlink()
        self._documents.clear()
        self._records.clear()
        self._retrieval_service = None

    @staticmethod
    def _summarize_sources(retrieval_response) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for result in retrieval_response.results:
            counts[result.source_type] += 1
        return dict(counts)
