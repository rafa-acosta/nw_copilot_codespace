# NW Copilot Academic Architecture Guide

## 1. Scope

This guide is the architectural companion to `COPILOT_UNDER_THE_HOOD_GUIDE.md`.

The first guide explains the runtime journey from GUI startup to grounded answer.

This guide explains the system from a more academic point of view:

- package by package
- module by module
- class by class at the important boundaries
- why the abstractions exist
- how the major objects collaborate

The goal is to help a new engineering team answer four questions:

- What are the layers of the copilot?
- What does each module own?
- Which classes are domain models, orchestrators, adapters, or utilities?
- Where should a future change be implemented?

## 2. Architectural Thesis

This project is a local retrieval-augmented copilot built as a layered Python application.

The main architectural idea is:

- ingestion is separated from processing
- processing is separated from retrieval
- retrieval is separated from answer generation
- GUI concerns are separated from core retrieval logic

This separation gives the project four useful properties:

- new document formats can be added without changing the chat server
- retrieval strategies can evolve without rewriting ingestion
- answer generation can switch between local extractive mode and Ollama-backed mode
- the GUI can stay thin because most logic lives in `CopilotApplicationService`

## 3. Layered View

```text
Layer 1: Presentation
    copilot_ui/static/index.html
    copilot_ui/static/app.js
    copilot_ui/static/styles.css

Layer 2: Transport / API
    copilot_ui/server.py

Layer 3: Application Service
    copilot_ui/services.py

Layer 4: Domain Services
    copilot_ui/loaders.py
    domain_routing/*
    rag_processing/*
    retrieval/*
    copilot_ui/answers.py
    copilot_ui/embeddings.py
    copilot_ui/ollama.py

Layer 5: Persistence / Index
    retrieval/retrievers/chroma_store.py
    storage_dir/uploads
    storage_dir/chroma

Layer 6: Core Data Models
    copilot_ui/models.py
    rag_processing/models.py
    retrieval/models/*
    domain_routing/models.py
```

## 4. Dependency View

```text
Browser
  -> copilot_ui.server
     -> copilot_ui.services
        -> copilot_ui.loaders
           -> rag_data_ingestion
        -> rag_processing
        -> domain_routing
        -> retrieval
        -> copilot_ui.embeddings
        -> copilot_ui.answers
           -> copilot_ui.ollama
```

The dependency direction is mostly inward:

- the browser depends on the API
- the API depends on the service layer
- the service layer depends on specialized subsystems
- the specialized subsystems mostly depend on data models and utilities

## 5. Core Object Graph

```text
CopilotRequestHandler
    owns a reference to
CopilotApplicationService
    owns
    - DocumentPipeline
    - DomainRouter
    - embedding_model
    - answer_generator
    - OllamaClient
    - current RetrievalService
    - in-memory document registry
    - in-memory record list
    - on-disk Chroma collection

RetrievalService
    owns
    - QueryProcessor
    - QueryEmbedder
    - VectorRetriever
    - KeywordRetriever
    - HybridRetriever
    - Reranker
    - RetrievalConfig

DocumentPipeline
    resolves and uses
    - StructureExtractor
    - Chunker
    - MetadataEnricher
```

## 6. High-Level Class Diagram

```text
BaseDataLoader <|-- TextFileLoader
BaseDataLoader <|-- PDFLoader
BaseDataLoader <|-- DocxLoader
BaseDataLoader <|-- ExcelLoader
BaseDataLoader <|-- JSONLoader
BaseDataLoader <|-- WebLoader
BaseDataLoader <|-- CiscoConfigLoader

StructureExtractor <|-- TextStructureExtractor
StructureExtractor <|-- PdfStructureExtractor
StructureExtractor <|-- WebStructureExtractor
StructureExtractor <|-- DocxStructureExtractor
StructureExtractor <|-- ExcelStructureExtractor
StructureExtractor <|-- JsonStructureExtractor
StructureExtractor <|-- CiscoStructureExtractor

Chunker <|-- TextChunker
Chunker <|-- WebChunker
Chunker <|-- DocxChunker
Chunker <|-- PdfChunker
Chunker <|-- ExcelChunker
Chunker <|-- JsonChunker
Chunker <|-- CiscoChunker

MetadataEnricher <|-- DefaultMetadataEnricher
DefaultMetadataEnricher <|-- PdfMetadataEnricher
DefaultMetadataEnricher <|-- ExcelMetadataEnricher
DefaultMetadataEnricher <|-- JsonMetadataEnricher
DefaultMetadataEnricher <|-- CiscoMetadataEnricher

QueryEmbedder <|-- CallableQueryEmbedder
QueryProcessor <|-- TechnicalQueryProcessor
Retriever <|-- VectorRetriever
Retriever <|-- KeywordRetriever
Retriever <|-- HybridRetriever
Reranker <|-- HeuristicReranker
VectorStore <|-- InMemoryVectorStore
VectorStore <|-- ChromaVectorStore

AnswerGenerator <|-- GroundedAnswerGenerator
GroundedAnswerGenerator <|-- OllamaAnswerGenerator

CopilotRequestHandler --> CopilotApplicationService
CopilotApplicationService --> DocumentPipeline
CopilotApplicationService --> DomainRouter
CopilotApplicationService --> RetrievalService
CopilotApplicationService --> HashingEmbeddingModel
CopilotApplicationService --> OllamaEmbeddingModel
CopilotApplicationService --> GroundedAnswerGenerator
CopilotApplicationService --> OllamaAnswerGenerator
CopilotApplicationService --> OllamaClient

DocumentPipeline --> ProcessorRegistry
ProcessorRegistry --> StructureExtractor
ProcessorRegistry --> Chunker
ProcessorRegistry --> MetadataEnricher

RetrievalService --> TechnicalQueryProcessor
RetrievalService --> VectorRetriever
RetrievalService --> KeywordRetriever
RetrievalService --> HybridRetriever
RetrievalService --> HeuristicReranker
VectorRetriever --> VectorStore
KeywordRetriever --> VectorStore
HybridRetriever --> VectorRetriever
HybridRetriever --> KeywordRetriever
```

## 7. Package Inventory

### 7.1 `copilot_ui/`

This package is the presentation-facing backend of the copilot. It bridges the browser with the indexing, retrieval, and answer-generation subsystems.

- `copilot_ui/__init__.py`
  Package facade. Re-exports the public runtime surface: answer generators, embedding adapters, `OllamaClient`, `run_server`, `CopilotApplicationService`, and `QueryOptions`.

- `copilot_ui/models.py`
  Backend/frontend contract models. This file defines the dataclasses that cross the service boundary.
  Main classes: `UploadedFilePayload`, `IndexedDocumentSummary`, `IndexedDocument`, `ChatCitation`, `ChatMessage`, `GeneratedAnswer`, `OllamaSettings`, `AppSnapshot`.

- `copilot_ui/ollama.py`
  Thin HTTP adapter for a local Ollama daemon.
  Main classes: `OllamaError`, `OllamaClient`.
  Architectural role: infrastructure adapter.

- `copilot_ui/embeddings.py`
  Embedding adapters used by the service layer.
  Main classes: `HashingEmbeddingModel`, `OllamaEmbeddingModel`.
  Architectural role: model adapter layer between the application and retrieval.

- `copilot_ui/answers.py`
  Answer synthesis layer.
  Main classes: `AnswerGenerator`, `GroundedAnswerGenerator`, `OllamaAnswerGenerator`.
  Architectural role: transforms retrieval output into user-facing chat content.

- `copilot_ui/loaders.py`
  Loader dispatch module that maps a file path to a concrete ingestion loader.
  Main functions: `is_probable_cisco_config()`, `load_document()`.
  Architectural role: anti-corruption boundary between GUI uploads and ingestion internals.

- `copilot_ui/services.py`
  Main application orchestrator.
  Main classes: `QueryOptions`, `CopilotApplicationService`.
  Architectural role: the stateful service layer that owns documents, chunks, retrieval service, and chat messages.

- `copilot_ui/server.py`
  Local HTTP transport layer.
  Main functions: `_json_response()`, `_read_json()`, `make_handler()`, `run_server()`.
  Main class: `CopilotRequestHandler`.
  Architectural role: API adapter over `CopilotApplicationService`.

- `copilot_ui/static/index.html`
  GUI markup and DOM skeleton.

- `copilot_ui/static/app.js`
  Frontend controller. Owns browser state, calls API routes, renders messages and citations, and handles upload/chat interactions.

- `copilot_ui/static/styles.css`
  Presentation styling for the local web GUI.

### 7.2 `domain_routing/`

This package decides whether a document or query belongs to `general`, `legal`, `medical`, or `cisco`.

- `domain_routing/__init__.py`
  Public package facade for routing exports.

- `domain_routing/models.py`
  Domain routing result models.
  Main classes: `DomainDetectionResult`, `DomainRouteDecision`.
  Architectural role: immutable routing outputs.

- `domain_routing/classifier.py`
  Weighted heuristic classifier.
  Main classes: `DomainSignalProfile`, `DomainClassifier`.
  Main helper functions: `_normalize_token()`, `_normalize_tokens()`.
  Architectural role: scoring engine for document and query domains.

- `domain_routing/router.py`
  Query-time routing policy.
  Main class: `DomainRouter`.
  Architectural role: converts classification results into a routing decision with filter policy.

- `domain_routing/prompting.py`
  Domain-specific prompt profiles used by answer generation.
  Main class: `DomainPromptProfile`.
  Main function: `prompt_profile_for()`.
  Architectural role: lets the answer layer adapt its wording to the routed domain.

### 7.3 `rag_data_ingestion/`

This package normalizes raw external sources into `IngestedData`.

- `rag_data_ingestion/__init__.py`
  Public ingestion API. Registers loaders into `LoaderFactory`.

- `rag_data_ingestion/base.py`
  Ingestion abstraction layer.
  Main classes: `IngestSource`, `IngestedData`, `BaseDataLoader`, `LoaderFactory`.
  Architectural role: defines the loader contract and the factory pattern used by demos and tooling.

- `rag_data_ingestion/cleaning.py`
  Generic text cleanup functions and the composable `TextCleaner`.
  Main functions: `normalize_unicode()`, `remove_extra_whitespace()`, `remove_special_characters()`, `convert_to_lowercase()`, `expand_contractions()`, `remove_urls()`, `remove_emails()`.
  Main class: `TextCleaner`.

- `rag_data_ingestion/utils.py`
  Generic file and chunking helpers.
  Main functions: `validate_file_exists()`, `validate_file_extension()`, `get_file_size()`, `read_file_safely()`, `sanitize_text()`, `chunk_text()`.

- `rag_data_ingestion/text_loader.py`
  Plain text loader.
  Main class: `TextFileLoader`.
  Architectural role: converts local text files into cleaned `IngestedData`.

- `rag_data_ingestion/pdf_loader.py`
  PDF loader and text extractor.
  Main class: `PDFLoader`.
  Architectural role: extracts page-aware content and metadata from PDFs.

- `rag_data_ingestion/web_loader.py`
  URL loader.
  Main class: `WebLoader`.
  Architectural role: fetches web pages and turns them into cleaned textual content.

- `rag_data_ingestion/docx_loader.py`
  Word document loader.
  Main class: `DocxLoader`.
  Architectural role: extracts paragraph and table content from DOCX files.

- `rag_data_ingestion/excel_loader.py`
  Excel loader.
  Main class: `ExcelLoader`.
  Architectural role: turns sheets and rows into flat textual content with spreadsheet metadata.

- `rag_data_ingestion/json_loader.py`
  JSON loader.
  Main class: `JSONLoader`.
  Architectural role: flattens nested JSON into searchable path/value lines.

- `rag_data_ingestion/cisco_loader.py`
  Cisco configuration loader.
  Main class: `CiscoConfigLoader`.
  Architectural role: normalizes network configuration text and optionally organizes or redacts it.

### 7.4 `rag_processing/`

This package converts cleaned documents into structured, metadata-rich chunks.

- `rag_processing/__init__.py`
  Public processing API facade.

- `rag_processing/base.py`
  Abstract processing contracts.
  Main classes: `StructureExtractor`, `Chunker`, `MetadataEnricher`.
  Architectural role: interface layer for the processing pipeline.

- `rag_processing/models.py`
  Core processing models.
  Main classes: `CleanDocument`, `StructuralNode`, `StructuredDocument`, `Metadata`, `Chunk`.
  Main helper: `_new_id()`.
  Architectural role: internal domain model for extraction and chunking.

- `rag_processing/utils.py`
  Structure-aware chunking helpers.
  Main functions: `split_lines()`, `split_paragraphs()`, `split_sentences()`, `is_heading()`, `chunk_units()`, `slice_lines_with_indices()`.

- `rag_processing/extractors.py`
  Source-type-specific structure extraction.
  Main classes: `TextStructureExtractor`, `PdfStructureExtractor`, `WebStructureExtractor`, `DocxStructureExtractor`, `ExcelStructureExtractor`, `JsonStructureExtractor`, `CiscoStructureExtractor`.
  Architectural role: turn flat content into a typed structural tree.

- `rag_processing/chunkers.py`
  Source-type-specific chunk builders.
  Main classes: `TextChunker`, `WebChunker`, `DocxChunker`, `PdfChunker`, `ExcelChunker`, `JsonChunker`, `CiscoChunker`.
  Architectural role: translate structure into chunk text plus raw metadata.

- `rag_processing/enrichers.py`
  Metadata enrichment layer.
  Main classes: `DefaultMetadataEnricher`, `PdfMetadataEnricher`, `ExcelMetadataEnricher`, `JsonMetadataEnricher`, `CiscoMetadataEnricher`.
  Architectural role: finalize `chunk_id`, ordering metadata, and propagated document metadata.

- `rag_processing/registry.py`
  Registry pattern that maps `source_type` to extractor/chunker/enricher triplets.
  Main class: `ProcessorRegistry`.

- `rag_processing/pipeline.py`
  End-to-end processing orchestrator.
  Main class: `DocumentPipeline`.
  Architectural role: the processing subsystem facade used by the application service.

### 7.5 `retrieval/`

This package owns query processing, vector search, keyword search, fusion, reranking, retrieval configuration, and retrieval result models.

#### 7.5.1 `retrieval/config/`

- `retrieval/config/__init__.py`
  Package facade for retrieval configuration.

- `retrieval/config/settings.py`
  Retrieval configuration model tree.
  Main classes: `QueryProcessingConfig`, `VectorRetrieverConfig`, `KeywordRetrieverConfig`, `HybridConfig`, `SourceTypeProfile`, `RerankerConfig`, `ObservabilityConfig`, `RetrievalConfig`.
  Main helper: `_default_source_profiles()`.
  Architectural role: typed configuration instead of loose dictionaries.

#### 7.5.2 `retrieval/embedders/`

- `retrieval/embedders/__init__.py`
  Public embedder exports.

- `retrieval/embedders/base.py`
  Abstract query embedding contract.
  Main class: `QueryEmbedder`.

- `retrieval/embedders/callable.py`
  Adapter that wraps a Python callable as a `QueryEmbedder`.
  Main class: `CallableQueryEmbedder`.

#### 7.5.3 `retrieval/filters/`

- `retrieval/filters/__init__.py`
  Filter package exports.

- `retrieval/filters/metadata.py`
  Declarative metadata filtering engine.
  Main class: `MetadataFilter`.
  Architectural role: supports structured query filters before or after retrieval.

#### 7.5.4 `retrieval/models/`

- `retrieval/models/__init__.py`
  Model package facade.

- `retrieval/models/filters.py`
  Filter dataclasses.
  Main classes: `NumericRange`, `MetadataFilterSpec`.

- `retrieval/models/query.py`
  Query-side models.
  Main classes: `RetrievalMode`, `QueryHints`, `ProcessedQuery`, `RetrievalRequest`.

- `retrieval/models/records.py`
  Indexed record models.
  Main classes: `ChunkMetadata`, `StoredChunk`.
  Main helpers: `_as_tuple()`, `_safe_filename()`, `_get_nested()`, `infer_embedding_dimension()`.

- `retrieval/models/results.py`
  Retrieval-side response models.
  Main classes: `RetrievalTraceStep`, `ScoredChunkCandidate`, `RetrievedChunk`, `RetrievalTiming`, `RetrievalDebugInfo`, `RetrievalResponse`.

#### 7.5.5 `retrieval/query_processing/`

- `retrieval/query_processing/__init__.py`
  Package facade for query processors.

- `retrieval/query_processing/base.py`
  Abstract query processor contract.
  Main class: `QueryProcessor`.

- `retrieval/query_processing/processor.py`
  Production query processor.
  Main class: `TechnicalQueryProcessor`.
  Architectural role: preserves technical syntax while still producing tokens, quoted phrases, expansions, and hints.

#### 7.5.6 `retrieval/retrievers/`

- `retrieval/retrievers/__init__.py`
  Public retriever exports.

- `retrieval/retrievers/base.py`
  Abstract retrieval contract.
  Main class: `Retriever`.

- `retrieval/retrievers/store.py`
  Vector store abstraction and in-memory reference implementation.
  Main classes: `VectorStore`, `InMemoryVectorStore`.

- `retrieval/retrievers/vector.py`
  Dense retrieval wrapper over a `VectorStore`.
  Main class: `VectorRetriever`.

- `retrieval/retrievers/keyword.py`
  Lexical retrieval engine over stored chunks.
  Main class: `KeywordRetriever`.
  Architectural role: exact phrase and technical-term friendly retrieval.

- `retrieval/retrievers/hybrid.py`
  Fusion retriever.
  Main class: `HybridRetriever`.
  Architectural role: combine dense and keyword evidence into one ranked list.

- `retrieval/retrievers/chroma_store.py`
  Persistent local Chroma-backed vector store.
  Main class: `ChromaVectorStore`.
  Architectural role: persistence boundary for chunk embeddings and metadata.

#### 7.5.7 `retrieval/rerankers/`

- `retrieval/rerankers/__init__.py`
  Public reranker exports.

- `retrieval/rerankers/base.py`
  Abstract reranking contract.
  Main class: `Reranker`.

- `retrieval/rerankers/heuristic.py`
  Post-retrieval reranking logic.
  Main class: `HeuristicReranker`.
  Architectural role: inject source-specific and metadata-specific boosts after candidate retrieval.

#### 7.5.8 `retrieval/services/`

- `retrieval/services/__init__.py`
  Public service builder exports.

- `retrieval/services/builders.py`
  Integration helpers that wire chunks, vector stores, retrievers, and rerankers.
  Main functions: `build_stored_chunks()`, `build_retrieval_service()`.

- `retrieval/services/retrieval_service.py`
  Retrieval orchestration service.
  Main class: `RetrievalService`.
  Architectural role: the facade for query processing, retrieval, reranking, tracing, and result formatting.

#### 7.5.9 `retrieval/utils/`

- `retrieval/utils/__init__.py`
  Utility package facade.

- `retrieval/utils/logging.py`
  Logger configuration helper.
  Main function: `configure_logger()`.

- `retrieval/utils/scoring.py`
  Score math helpers.
  Main functions: `cosine_similarity()`, `min_max_normalize()`, `weighted_sum()`, `reciprocal_rank_score()`, `validate_vector_dimension()`.

- `retrieval/utils/text.py`
  Query normalization and technical token utilities.
  Main functions: `unique_preserve_order()`, `normalize_unicode()`, `collapse_whitespace()`, `normalize_user_query()`, `normalize_for_lookup()`, `extract_quoted_phrases()`, `tokenize_preserving_technical()`, `extract_technical_terms()`, `infer_query_hints()`, `contains_term()`, `extract_sheet_headers()`.

- `retrieval/utils/timing.py`
  Timing helper for stage traces.
  Main class: `StageTimer`.

### 7.6 Test Modules

These are not runtime packages, but they explain how the maintainers intended the system to behave.

- `tests/test_rag_processing.py`
  Verifies extraction and chunking behavior by source type.

- `tests/test_pdf_loader.py`
  Verifies PDF ingestion edge cases.

- `tests/test_domain_routing.py`
  Verifies automatic and manual domain routing decisions.

- `tests/test_copilot_ui.py`
  Verifies service behavior, indexing, inspection, and chat integration.

- `retrieval/tests/test_retrieval_pipeline.py`
  Verifies dense, keyword, hybrid, and filter behavior inside the retrieval layer.

## 8. Architectural Patterns Used

### 8.1 Facade Pattern

Used in:

- `copilot_ui/__init__.py`
- `rag_data_ingestion/__init__.py`
- `retrieval/services/builders.py`
- `rag_processing/pipeline.py`

Why it matters:

- hides subsystem complexity
- gives callers a short import path
- makes demos and integration code cleaner

### 8.2 Factory Pattern

Used in:

- `LoaderFactory` in `rag_data_ingestion/base.py`

Why it matters:

- lets the system instantiate loaders by source type
- reduces branching in demo code and utilities

### 8.3 Registry Pattern

Used in:

- `ProcessorRegistry` in `rag_processing/registry.py`

Why it matters:

- decouples `DocumentPipeline` from concrete processor classes
- makes source-type extensions local and explicit

### 8.4 Adapter Pattern

Used in:

- `OllamaClient`
- `OllamaEmbeddingModel`
- `HashingEmbeddingModel`
- `CallableQueryEmbedder`
- `OllamaAnswerGenerator`

Why it matters:

- local models and retrieval internals speak different interfaces
- adapters isolate transport and third-party API details

### 8.5 Strategy Pattern

Used in:

- retrievers: dense, keyword, hybrid
- answer generators: grounded vs Ollama-backed
- embedders: hashing vs Ollama

Why it matters:

- behavior can change without rewriting the caller
- `CopilotApplicationService` stays orchestration-focused

### 8.6 Data Transfer Objects

Used in:

- `AppSnapshot`
- `ChatMessage`
- `ChatCitation`
- `GeneratedAnswer`
- `RetrievedChunk`
- `RetrievalResponse`

Why it matters:

- transport shape stays stable
- frontend and backend communicate through explicit contracts

## 9. Stateful vs Stateless Components

### 9.1 Mostly Stateful Components

- `CopilotApplicationService`
- `OllamaClient` session
- `KeywordRetriever` in-memory lexical index
- `ChromaVectorStore`
- `StageTimer`
- browser `state` object in `app.js`

### 9.2 Mostly Stateless or Pure-ish Components

- `TextCleaner`
- `DomainClassifier`
- `TechnicalQueryProcessor`
- `MetadataFilter`
- scoring helpers in `retrieval/utils/scoring.py`
- text helpers in `retrieval/utils/text.py`

Why this distinction matters:

- stateful components are where lifecycle bugs usually appear
- stateless components are easier to unit test and reuse

## 10. Extension Points

### 10.1 Add a New Document Type

You would usually touch:

- one new loader in `rag_data_ingestion/`
- one extractor in `rag_processing/extractors.py`
- one chunker in `rag_processing/chunkers.py`
- optionally one enricher in `rag_processing/enrichers.py`
- one registry entry in `rag_processing/registry.py`
- one dispatch rule in `copilot_ui/loaders.py`

### 10.2 Add a New Domain

You would usually touch:

- `domain_routing/models.py`
- `domain_routing/classifier.py`
- `domain_routing/prompting.py`
- possibly GUI controls if the domain should be selectable manually

### 10.3 Add a New Embedding Provider

You would usually touch:

- `copilot_ui/embeddings.py`
- maybe `copilot_ui/services.py`
- maybe `retrieval/embedders/` if a lower-level query embedder abstraction is needed

### 10.4 Add a New Retrieval Strategy

You would usually touch:

- `retrieval/retrievers/base.py`
- a new retriever module
- `retrieval/services/retrieval_service.py`
- `retrieval/services/builders.py`
- maybe `RetrievalMode` in `retrieval/models/query.py`

## 11. What Is the True Center of the System?

The technical center of gravity is `CopilotApplicationService`.

Why:

- it owns state
- it receives uploads
- it triggers indexing
- it rebuilds retrieval
- it routes queries
- it delegates answer generation
- it returns the snapshots that drive the GUI

The conceptual center of gravity is the combination of:

- `DocumentPipeline`
- `RetrievalService`

Why:

- one turns documents into chunks
- the other turns queries into ranked evidence

The quality of the copilot depends mostly on those two layers.

## 12. Suggested Reading Order for Junior Engineers

Read in this order:

1. `copilot_ui/services.py`
2. `copilot_ui/server.py`
3. `copilot_ui/loaders.py`
4. `rag_data_ingestion/base.py`
5. `rag_processing/pipeline.py`
6. `rag_processing/registry.py`
7. `rag_processing/extractors.py`
8. `rag_processing/chunkers.py`
9. `retrieval/services/builders.py`
10. `retrieval/services/retrieval_service.py`
11. `retrieval/retrievers/vector.py`
12. `retrieval/retrievers/keyword.py`
13. `retrieval/retrievers/hybrid.py`
14. `retrieval/rerankers/heuristic.py`
15. `copilot_ui/answers.py`
16. `domain_routing/classifier.py`
17. `copilot_ui/ollama.py`

This order follows the actual runtime path while still preserving subsystem boundaries.

## 13. Short Mental Model

If a junior engineer remembers only one summary, it should be this:

```text
raw file
  -> loader
  -> clean document
  -> structured document
  -> chunk list
  -> stored chunks with embeddings
  -> Chroma + keyword index
  -> routed query
  -> retrieved evidence
  -> reranked evidence
  -> grounded answer
```

That is the full copilot in one line.
