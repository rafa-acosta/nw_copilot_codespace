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
from domain_routing import DomainRouter, SUPPORTED_DOMAINS
from evaluation import RagasEvaluationPayload, RagasEvaluator, RagasEvaluatorConfig
from rag_processing import CleanDocument, DocumentPipeline
from retrieval import MetadataFilterSpec, RetrievalConfig, RetrievalMode, RetrievalRequest
from retrieval.retrievers import ChromaVectorStore
from retrieval.services import build_retrieval_service, build_stored_chunks
from retrieval.utils import extract_sheet_headers


@dataclass(slots=True)
class QueryOptions:
    """Query controls exposed to the frontend."""

    mode: str = RetrievalMode.HYBRID.value
    top_k: int = 4
    domain: str = "auto"
    source_types: tuple[str, ...] = ()
    debug: bool = False


class CopilotApplicationService:
    """Owns document indexing, retrieval, and chat state for the GUI."""

    CHROMA_COLLECTION_NAME = "nw_copilot_chunks"
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
    SUPPORTED_DOMAINS = SUPPORTED_DOMAINS

    def __init__(
        self,
        *,
        storage_dir: str | Path | None = None,
        retrieval_config: RetrievalConfig | None = None,
        embedding_model: HashingEmbeddingModel | OllamaEmbeddingModel | None = None,
        answer_generator: AnswerGenerator | None = None,
        ollama_client: OllamaClient | None = None,
        ragas_evaluator: object | None = None,
    ) -> None:
        self.storage_dir = Path(storage_dir or "/tmp/nw_copilot_ui")
        self.upload_dir = self.storage_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path = self.storage_dir / "chroma"

        self.retrieval_config = retrieval_config or RetrievalConfig()
        self.processing_pipeline = DocumentPipeline(max_size=900, overlap=120)
        self.domain_router = DomainRouter()
        self._lock = threading.RLock()
        self._documents: dict[str, IndexedDocument] = {}
        self._records = []
        self._messages: list[ChatMessage] = []
        self._retrieval_service = None
        self._evaluation_payloads: dict[str, RagasEvaluationPayload] = {}
        self._ragas_evaluator = ragas_evaluator
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
            self._reconcile_ollama_models_locked()

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
            self._evaluation_payloads.clear()
            return self._snapshot_locked()

    def refresh_ollama_models(self) -> AppSnapshot:
        with self._lock:
            self._refresh_ollama_models_locked()
            self._reconcile_ollama_models_locked()
            return self._snapshot_locked()

    def update_ollama_settings(
        self,
        *,
        chat_model: str | None = None,
        embedding_model: str | None = None,
    ) -> AppSnapshot:
        with self._lock:
            if self.ollama_client is None:
                raise ValueError("Ollama settings are unavailable for the current backend configuration")

            next_chat_model = (chat_model or self.ollama_client.chat_model).strip()
            next_embedding_model = (embedding_model or self.ollama_client.embedding_model).strip()
            if not next_chat_model:
                raise ValueError("Chat model is required")
            if not next_embedding_model:
                raise ValueError("Embedding model is required")

            self._refresh_ollama_models_locked(suppress_errors=True)
            pulled_models = []
            for model_name in dict.fromkeys((next_chat_model, next_embedding_model)):
                if self._ensure_model_available_locked(model_name):
                    pulled_models.append(model_name)

            next_client = self.ollama_client.with_models(
                chat_model=next_chat_model,
                embedding_model=next_embedding_model,
            )
            next_embedding_adapter = OllamaEmbeddingModel(client=next_client)
            next_answer_generator = OllamaAnswerGenerator(client=next_client)
            embedding_changed = next_embedding_model != self.ollama_client.embedding_model
            chat_changed = next_chat_model != self.ollama_client.chat_model

            if embedding_changed and self._documents:
                rebuilt_records, rebuilt_documents = self._reindex_documents_with_model_locked(next_embedding_adapter)
                self._records = rebuilt_records
                self._documents = rebuilt_documents
                self._rebuild_retrieval_service_with_embedder(next_embedding_adapter)
            elif embedding_changed and self._records:
                self._rebuild_retrieval_service_with_embedder(next_embedding_adapter)

            self.embedding_model = next_embedding_adapter
            self.answer_generator = next_answer_generator
            self.ollama_client = next_client
            self._refresh_ollama_models_locked(suppress_errors=True)

            if pulled_models:
                pulled_summary = ", ".join(pulled_models)
                self._last_upload_message = f"Pulled Ollama model(s): {pulled_summary}"
            elif chat_changed or embedding_changed:
                self._last_upload_message = None
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

            manual_domain = options.domain.strip().casefold()
            if manual_domain == "auto":
                manual_domain = None
            elif manual_domain:
                self.domain_router.validate_domain(manual_domain)

            route = self.domain_router.route_query(
                message,
                manual_domain=manual_domain,
                available_domain_counts=self._available_domain_counts_locked(),
            )
            filters = self._build_filters(options=options, route_domain=route.domain, apply_domain_filter=route.filter_applied)

            retrieval_response = self._retrieval_service.retrieve(
                RetrievalRequest(
                    query=message,
                    top_k=options.top_k,
                    mode=RetrievalMode(options.mode),
                    filters=filters,
                    debug=options.debug,
                    domain=route.domain,
                    domain_confidence=route.confidence,
                    domain_reason=route.reason,
                    domain_mode=route.mode,
                    domain_filter_applied=route.filter_applied,
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
            if retrieval_response.results and generated.content.strip():
                assistant_message.meta["ragas_available"] = True
                assistant_message.meta["ragas_evaluated"] = False
                self._evaluation_payloads[assistant_message.message_id] = self._build_evaluation_payload(
                    query=message,
                    response=generated.content,
                    retrieval_response=retrieval_response,
                )
            self._messages.append(assistant_message)
            return self._snapshot_locked()

    def snapshot(self) -> AppSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def evaluate_message(
        self,
        message_id: str,
        *,
        reference: str | None = None,
        metrics: tuple[str, ...] = (),
    ) -> AppSnapshot:
        with self._lock:
            payload = self._evaluation_payloads.get(message_id)
            if payload is None:
                raise ValueError("No RAGAS evaluation payload is available for that message.")
            payload = payload.with_reference(reference)
            evaluator = self._resolve_ragas_evaluator_locked()

        result = evaluator.evaluate(payload, metrics=metrics or None)

        with self._lock:
            message = self._find_message_locked(message_id)
            if message is None:
                raise ValueError("Message no longer exists.")
            message.meta["ragas"] = result.to_dict()
            message.meta["ragas_evaluated"] = True
            return self._snapshot_locked()

    def inspect_vector_records(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        include_embeddings: bool = False,
    ) -> dict[str, object]:
        with self._lock:
            return self._inspect_vector_records_locked(
                limit=limit,
                offset=offset,
                include_embeddings=include_embeddings,
            )

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

    def _inspect_vector_records_locked(
        self,
        *,
        limit: int,
        offset: int,
        include_embeddings: bool,
    ) -> dict[str, object]:
        vector_store = self._current_vector_store_locked()
        if vector_store is None:
            vector_store = ChromaVectorStore(
                persist_directory=self.chroma_path,
                collection_name=self.CHROMA_COLLECTION_NAME,
            )
        return vector_store.peek_records(
            limit=max(1, limit),
            offset=max(0, offset),
            include_embeddings=include_embeddings,
        )

    def _current_vector_store_locked(self) -> ChromaVectorStore | None:
        if self._retrieval_service is None or self._retrieval_service.vector_retriever is None:
            return None
        vector_store = self._retrieval_service.vector_retriever.vector_store
        return vector_store if isinstance(vector_store, ChromaVectorStore) else None

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
        if models:
            self._ollama_last_error = None
        else:
            self._ollama_last_error = (
                f'No local Ollama models were found. Pull one with `ollama pull {FIXED_OLLAMA_MODEL}`.'
            )
        return models

    def _reconcile_ollama_models_locked(self) -> None:
        if self.ollama_client is None or not self._ollama_available_models:
            return

        next_chat_model = self.ollama_client.chat_model
        next_embedding_model = self.ollama_client.embedding_model
        if next_chat_model not in self._ollama_available_models:
            next_chat_model = self._choose_chat_fallback(self._ollama_available_models)
        if next_embedding_model not in self._ollama_available_models:
            next_embedding_model = self._choose_embedding_fallback(self._ollama_available_models)

        if (
            next_chat_model == self.ollama_client.chat_model
            and next_embedding_model == self.ollama_client.embedding_model
        ):
            return

        self.ollama_client = self.ollama_client.with_models(
            chat_model=next_chat_model,
            embedding_model=next_embedding_model,
        )
        if isinstance(self.embedding_model, OllamaEmbeddingModel):
            self.embedding_model = OllamaEmbeddingModel(client=self.ollama_client)
        if isinstance(self.answer_generator, OllamaAnswerGenerator):
            self.answer_generator = OllamaAnswerGenerator(client=self.ollama_client)

    def _ensure_model_available_locked(self, model_name: str) -> bool:
        if not model_name.strip():
            raise ValueError("Ollama model name is required")
        if self.ollama_client is None:
            raise ValueError("Ollama settings are unavailable for the current backend configuration")

        if model_name in self._ollama_available_models:
            return False

        self.ollama_client.pull_model(model_name)
        self._refresh_ollama_models_locked()
        if model_name not in self._ollama_available_models:
            raise ValueError(f'Ollama model "{model_name}" could not be loaded from the local Ollama repository.')
        return True

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
        clean_document.metadata["filename"] = display_name
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
                domain=clean_document.metadata.get("domain"),
                domain_confidence=clean_document.metadata.get("domain_confidence"),
                domain_reason=clean_document.metadata.get("domain_reason"),
            )
        else:
            summary = IndexedDocumentSummary(
                document_id=existing_summary.document_id,
                filename=display_name,
                file_path=str(file_path),
                source_type=clean_document.source_type,
                chunk_count=len(stored_chunks),
                domain=clean_document.metadata.get("domain"),
                domain_confidence=clean_document.metadata.get("domain_confidence"),
                domain_reason=clean_document.metadata.get("domain_reason"),
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
            self._clear_chroma_index_locked()
            self._retrieval_service = None
            return
        self._retrieval_service = build_retrieval_service(
            self._records,
            query_embedder=self.embedding_model.as_query_embedder(),
            config=self.retrieval_config,
            chroma_path=self.chroma_path,
            collection_name=self.CHROMA_COLLECTION_NAME,
        )

    def _rebuild_retrieval_service_with_embedder(self, embedding_model: OllamaEmbeddingModel) -> None:
        if not self._records:
            self._clear_chroma_index_locked()
            self._retrieval_service = None
            return
        self._retrieval_service = build_retrieval_service(
            self._records,
            query_embedder=embedding_model.as_query_embedder(),
            config=self.retrieval_config,
            chroma_path=self.chroma_path,
            collection_name=self.CHROMA_COLLECTION_NAME,
        )

    def _clear_chroma_index_locked(self) -> None:
        ChromaVectorStore.clear_collection(self.chroma_path, self.CHROMA_COLLECTION_NAME)

    def _clear_documents_locked(self) -> None:
        for indexed in self._documents.values():
            path = Path(indexed.temp_path)
            if path.exists():
                path.unlink()
        self._documents.clear()
        self._records.clear()
        self._clear_chroma_index_locked()
        self._retrieval_service = None

    def _resolve_ragas_evaluator_locked(self) -> object:
        if self._ragas_evaluator is not None:
            return self._ragas_evaluator

        if RagasEvaluatorConfig.has_env_override():
            return RagasEvaluator(RagasEvaluatorConfig.from_env())

        if self.ollama_client is not None:
            config = RagasEvaluatorConfig.from_ollama(
                base_url=self.ollama_client.base_url,
                chat_model=self.ollama_client.chat_model,
                embedding_model=self.ollama_client.embedding_model,
            )
            return RagasEvaluator(config)

        return RagasEvaluator()

    @staticmethod
    def _build_evaluation_payload(
        *,
        query: str,
        response: str,
        retrieval_response,
    ) -> RagasEvaluationPayload:
        results = retrieval_response.results
        return RagasEvaluationPayload(
            user_input=query,
            response=response,
            retrieved_contexts=tuple(result.text for result in results),
            retrieved_context_ids=tuple(result.chunk_id for result in results),
            retrieved_context_metadata=tuple(result.metadata for result in results),
            metadata={
                "retrieval_mode": retrieval_response.retrieval_mode,
                "domain": retrieval_response.domain,
                "domain_confidence": retrieval_response.domain_confidence,
                "domain_filter_applied": retrieval_response.domain_filter_applied,
            },
        )

    def _find_message_locked(self, message_id: str) -> ChatMessage | None:
        for message in self._messages:
            if message.message_id == message_id:
                return message
        return None

    def _reindex_documents_with_model_locked(
        self,
        embedding_model: OllamaEmbeddingModel,
    ) -> tuple[list, dict[str, IndexedDocument]]:
        rebuilt_records = []
        rebuilt_documents: dict[str, IndexedDocument] = {}
        current_documents = list(self._documents.values())

        for indexed in current_documents:
            summary, indexed_document, stored_chunks = self._index_document_from_path(
                file_path=Path(indexed.temp_path),
                display_name=indexed.summary.filename,
                existing_summary=indexed.summary,
                embedding_model=embedding_model,
            )
            rebuilt_records.extend(stored_chunks)
            rebuilt_documents[summary.document_id] = indexed_document

        return rebuilt_records, rebuilt_documents

    @staticmethod
    def _build_filters(
        *,
        options: QueryOptions,
        route_domain: str | None,
        apply_domain_filter: bool,
    ) -> MetadataFilterSpec | None:
        equals = {}
        any_of = {}

        if apply_domain_filter and route_domain:
            equals["domain"] = route_domain
        if options.source_types:
            any_of["source_type"] = options.source_types

        if not equals and not any_of:
            return None
        return MetadataFilterSpec(equals=equals, any_of=any_of)

    def _available_domain_counts_locked(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for indexed in self._documents.values():
            if indexed.summary.domain:
                counts[indexed.summary.domain] += 1
        return counts

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
    def _choose_chat_fallback(models: tuple[str, ...]) -> str:
        ranked = sorted(models, key=lambda model: CopilotApplicationService._chat_model_rank(model), reverse=True)
        return ranked[0]

    @staticmethod
    def _choose_embedding_fallback(models: tuple[str, ...]) -> str:
        ranked = sorted(models, key=lambda model: CopilotApplicationService._embedding_model_rank(model), reverse=True)
        return ranked[0]

    @staticmethod
    def _chat_model_rank(model_name: str) -> tuple[int, int, str]:
        lowered = model_name.casefold()
        score = 0
        if "llama" in lowered:
            score += 50
        if "qwen" in lowered:
            score += 45
        if "phi" in lowered:
            score += 40
        if "coder" in lowered:
            score += 10
        if "instruct" in lowered:
            score += 5
        return (score, -len(model_name), model_name)

    @staticmethod
    def _embedding_model_rank(model_name: str) -> tuple[int, int, str]:
        lowered = model_name.casefold()
        score = 0
        preferred_terms = (
            "embed",
            "embedding",
            "nomic",
            "mxbai",
            "bge",
            "e5",
            "snowflake",
            "arctic",
        )
        if any(term in lowered for term in preferred_terms):
            score += 100
        if "qwen" in lowered:
            score += 40
        if "phi" in lowered:
            score += 35
        if "llama" in lowered:
            score += 30
        if "coder" in lowered:
            score += 5
        return (score, -len(model_name), model_name)

    @staticmethod
    def _summarize_sources(retrieval_response) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for result in retrieval_response.results:
            counts[result.source_type] += 1
        return dict(counts)
