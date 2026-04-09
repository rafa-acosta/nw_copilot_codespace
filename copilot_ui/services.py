"""Application services for the local copilot GUI."""

from __future__ import annotations

import base64
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import threading
from uuid import uuid4

from copilot_ui.answers import AnswerGenerator, GroundedAnswerGenerator, OllamaAnswerGenerator
from copilot_ui.embeddings import HashingEmbeddingModel, OllamaEmbeddingModel
from copilot_ui.loaders import load_document
from copilot_ui.models import (
    AppSnapshot,
    ChatMessage,
    IndexedDocument,
    IndexedDocumentSummary,
    OllamaSettings,
    UploadedFilePayload,
)
from copilot_ui.ollama import FIXED_OLLAMA_MODEL, OllamaClient, OllamaError
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
        embedding_model: HashingEmbeddingModel | OllamaEmbeddingModel | None = None,
        answer_generator: AnswerGenerator | None = None,
        ollama_client: OllamaClient | None = None,
    ) -> None:
        self.storage_dir = Path(storage_dir or "/tmp/nw_copilot_ui")
        self.upload_dir = self.storage_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        self.retrieval_config = retrieval_config or RetrievalConfig()
        self.processing_pipeline = DocumentPipeline(max_size=900, overlap=120)
        self._lock = threading.RLock()
        self._documents: dict[str, IndexedDocument] = {}
        self._records = []
        self._messages: list[ChatMessage] = []
        self._retrieval_service = None
        self._ollama_available_models: tuple[str, ...] = ()
        self._ollama_last_error: str | None = None
        self._last_upload_message: str | None = None

        resolved_ollama_client = self._resolve_ollama_client(
            embedding_model=embedding_model,
            answer_generator=answer_generator,
            ollama_client=ollama_client,
        )
        self.ollama_client = resolved_ollama_client

        if embedding_model is not None:
            self.embedding_model = embedding_model
        elif self.ollama_client is not None:
            self.embedding_model = OllamaEmbeddingModel(client=self.ollama_client)
        else:
            self.embedding_model = HashingEmbeddingModel()

        if answer_generator is not None:
            self.answer_generator = answer_generator
        elif self.ollama_client is not None:
            self.answer_generator = OllamaAnswerGenerator(client=self.ollama_client)
        else:
            self.answer_generator = GroundedAnswerGenerator()

        if self.ollama_client is not None:
            self._refresh_ollama_models_locked(suppress_errors=True)

    def add_uploaded_files(self, payloads: list[UploadedFilePayload], *, clear_existing: bool = False) -> AppSnapshot:
        with self._lock:
            if clear_existing:
                self._clear_documents_locked()

            indexed_count = 0
            failures: list[str] = []
            for payload in payloads:
                try:
                    stored_path = self._persist_upload(payload)
                    summary, indexed_document, stored_chunks = self._index_document_from_path(
                        file_path=stored_path,
                        display_name=payload.name,
                    )
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{payload.name}: {exc}")
                    continue
                self._records.extend(stored_chunks)
                self._documents[summary.document_id] = indexed_document
                indexed_count += 1

            if indexed_count == 0 and failures:
                self._last_upload_message = None
                raise ValueError("\n".join(failures))

            self._rebuild_retrieval_service()
            if failures:
                self._last_upload_message = (
                    f"Indexed {indexed_count} file(s). Skipped {len(failures)} file(s): "
                    + " | ".join(failures)
                )
            else:
                self._last_upload_message = f"Indexed {indexed_count} file(s)."
            return self._snapshot_locked()

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
            return self._snapshot_locked()

    def clear_documents(self) -> AppSnapshot:
        with self._lock:
            self._clear_documents_locked()
            return self._snapshot_locked()

    def clear_chat(self) -> AppSnapshot:
        with self._lock:
            self._messages.clear()
            return self._snapshot_locked()

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
                return self._snapshot_locked()

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
            return self._snapshot_locked()

    def snapshot(self) -> AppSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def last_upload_message(self) -> str | None:
        with self._lock:
            return self._last_upload_message

    def _snapshot_locked(self) -> AppSnapshot:
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
            ollama=self._ollama_settings_locked(),
        )

    def _ollama_settings_locked(self) -> OllamaSettings | None:
        if self.ollama_client is None:
            return None

        return OllamaSettings(
            enabled=True,
            base_url=self.ollama_client.base_url,
            chat_model=self.ollama_client.chat_model,
            embedding_model=self.ollama_client.embedding_model,
            available_models=self._ollama_available_models,
            last_error=self._ollama_last_error,
        )

    def _persist_upload(self, payload: UploadedFilePayload) -> Path:
        safe_name = Path(payload.name).name or "upload.bin"
        target = self.upload_dir / f"{uuid4().hex}_{safe_name}"
        content = base64.b64decode(payload.content_base64.encode("utf-8"))
        target.write_bytes(content)
        return target

    def _refresh_ollama_models_locked(self, *, suppress_errors: bool = False) -> tuple[str, ...]:
        if self.ollama_client is None:
            self._ollama_available_models = ()
            self._ollama_last_error = None
            return ()

        try:
            models = self.ollama_client.list_models()
        except OllamaError as exc:
            self._ollama_available_models = ()
            self._ollama_last_error = str(exc)
            if suppress_errors:
                return ()
            raise

        self._ollama_available_models = models
        if FIXED_OLLAMA_MODEL in models:
            self._ollama_last_error = None
        else:
            self._ollama_last_error = (
                f'Required Ollama model "{FIXED_OLLAMA_MODEL}" is not installed. '
                f"Run `ollama pull {FIXED_OLLAMA_MODEL}`."
            )
        return models

    def _index_document_from_path(
        self,
        *,
        file_path: Path,
        display_name: str,
        existing_summary: IndexedDocumentSummary | None = None,
        embedding_model: HashingEmbeddingModel | OllamaEmbeddingModel | None = None,
    ) -> tuple[IndexedDocumentSummary, IndexedDocument, list]:
        active_embedding_model = embedding_model or self.embedding_model
        ingested = load_document(str(file_path))
        clean_document = CleanDocument.from_ingested(ingested)
        if existing_summary is not None:
            clean_document.document_id = existing_summary.document_id

        chunks = self.processing_pipeline.run(clean_document)
        embeddings = active_embedding_model.embed_documents([chunk.content for chunk in chunks])
        column_names = [
            extract_sheet_headers(chunk.content) if getattr(chunk.metadata, "sheet", None) else ()
            for chunk in chunks
        ]
        stored_chunks = build_stored_chunks(chunks, embeddings, column_names=column_names)
        for record in stored_chunks:
            record.metadata.filename = display_name

        if existing_summary is None:
            summary = IndexedDocumentSummary(
                document_id=clean_document.document_id,
                filename=display_name,
                file_path=str(file_path),
                source_type=clean_document.source_type,
                chunk_count=len(stored_chunks),
            )
        else:
            summary = IndexedDocumentSummary(
                document_id=existing_summary.document_id,
                filename=display_name,
                file_path=str(file_path),
                source_type=clean_document.source_type,
                chunk_count=len(stored_chunks),
                added_at=existing_summary.added_at,
            )
        chunk_ids = tuple(record.metadata.chunk_id or "" for record in stored_chunks)
        indexed_document = IndexedDocument(
            summary=summary,
            chunk_ids=chunk_ids,
            temp_path=str(file_path),
        )
        return summary, indexed_document, stored_chunks

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
    def _resolve_ollama_client(
        *,
        embedding_model: HashingEmbeddingModel | OllamaEmbeddingModel | None,
        answer_generator: AnswerGenerator | None,
        ollama_client: OllamaClient | None,
    ) -> OllamaClient | None:
        if ollama_client is not None:
            return ollama_client
        if isinstance(embedding_model, OllamaEmbeddingModel):
            return embedding_model.client
        if isinstance(answer_generator, OllamaAnswerGenerator):
            return answer_generator.client
        if embedding_model is None and answer_generator is None:
            return OllamaClient.from_env()
        return None

    @staticmethod
    def _summarize_sources(retrieval_response) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for result in retrieval_response.results:
            counts[result.source_type] += 1
        return dict(counts)
