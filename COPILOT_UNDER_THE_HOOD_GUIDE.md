# NW Copilot Under the Hood Guide

## 1. Purpose of This Guide

This guide explains how the copilot works from the moment the GUI starts until an answer is returned to the user.

It is written for junior engineers who are new to this repository and need to understand:

- the real runtime entrypoints
- the full call flow from GUI to answer
- the main functions and classes involved
- how to run each important layer from the terminal
- how to inspect what was indexed into Chroma

## 2. Important Reality Check

The current GUI is **not Streamlit**.

The GUI is a **local web application** made of:

- a shell launcher: `../run_copilot.sh`
- a Python HTTP server: `copilot_ui/server.py`
- a frontend in static files: `copilot_ui/static/index.html`, `styles.css`, `app.js`
- a backend service layer: `copilot_ui/services.py`

If someone says "run the Streamlit app", that is outdated for the current version of this project.

## 3. Recommended Working Setup

Run these commands first:

```bash
export ROOT=/home/rafa/Documents/AIML/Projects/nw-copilot-3-pipelines-v1
cd "$ROOT/nw_copilot_codespace"
export PY="$ROOT/venv/bin/python"
```

If you already activated the virtual environment, you can replace `$PY` with `python`.

## 4. The Real Entry Points

| Entry point | File | What it does | Command |
|---|---|---|---|
| Main launcher | `../run_copilot.sh` | Checks Ollama, resolves env vars, starts the GUI server | `cd "$ROOT" && ./run_copilot.sh` |
| Direct GUI launch | `examples/9_launch_copilot_ui.py` | Starts the local copilot web server directly | `cd "$ROOT/nw_copilot_codespace" && "$PY" examples/9_launch_copilot_ui.py` |
| Python server function | `copilot_ui.server.run_server()` | Creates `CopilotApplicationService` and starts `ThreadingHTTPServer` | See command in section 9.1 |
| Chroma inspector | `examples/10_inspect_chroma.py` | Shows chunks and embeddings stored in Chroma | See command in section 9.8 |

## 5. High-Level Architecture

```text
Browser UI (index.html + app.js)
        |
        v
HTTP routes in copilot_ui/server.py
        |
        v
CopilotApplicationService in copilot_ui/services.py
        |
        +--> Document loading (copilot_ui/loaders.py)
        |        |
        |        v
        |   rag_data_ingestion/*_loader.py
        |
        +--> Document processing (rag_processing/)
        |        |
        |        v
        |   extract -> chunk -> enrich metadata
        |
        +--> Embeddings (copilot_ui/embeddings.py)
        |
        +--> Chroma indexing (retrieval/retrievers/chroma_store.py)
        |
        +--> Query routing (domain_routing/)
        |
        +--> Retrieval orchestration (retrieval/services/retrieval_service.py)
        |        |
        |        +--> dense retrieval
        |        +--> keyword retrieval
        |        +--> hybrid fusion
        |        +--> reranking
        |
        +--> Answer generation (copilot_ui/answers.py)
                 |
                 +--> grounded extractive answer
                 +--> Ollama answer generation
```

## 6. End-to-End Flow From GUI Start to Answer

### 6.1 GUI Startup Flow

1. `../run_copilot.sh`
   Purpose: This is the real operational launcher.

2. `show_help()`
   Purpose: Prints usage and supported environment variables.

3. `check_ollama()`
   Purpose: Calls Ollama `/api/tags` to confirm the daemon is reachable before the GUI starts.

4. `copilot_ui.run_server(...)`
   File: `copilot_ui/__init__.py`
   Purpose: Re-exports `run_server` so the shell script can start the app with a clean import.

5. `copilot_ui.server.run_server(host, port, open_browser, service=None)`
   Purpose: Creates the backend service and starts `ThreadingHTTPServer`.

6. `CopilotApplicationService.__init__(...)`
   Purpose: Creates the application state, upload folder, Chroma path, processing pipeline, domain router, embedding model, answer generator, and Ollama client.

7. Browser requests `/`
   Handler: `CopilotRequestHandler.do_GET()`
   Purpose: Serves `index.html`.

8. Browser loads `app.js`
   Purpose: Initializes frontend state and starts the first call to `/api/state`.

9. `fetchState()`
   File: `copilot_ui/static/app.js`
   Purpose: Calls `/api/state` and hydrates the frontend with `applyState(...)`.

10. `CopilotApplicationService.snapshot()`
    Purpose: Returns `AppSnapshot` with documents, messages, chunk count, supported types, and Ollama config.

### 6.2 Upload and Indexing Flow

1. `uploadFiles(fileList)`
   File: `copilot_ui/static/app.js`
   Purpose: Converts browser files to base64 and sends them to `/api/documents/upload`.

2. `POST /api/documents/upload`
   File: `copilot_ui/server.py`
   Purpose: Converts JSON payload into `UploadedFilePayload` objects.

3. `UploadedFilePayload.from_dict(payload)`
   File: `copilot_ui/models.py`
   Purpose: Validates that each uploaded file has a name and base64 content.

4. `CopilotApplicationService.add_uploaded_files(payloads, clear_existing=False)`
   Purpose: Orchestrates the entire indexing flow for one or more files.

5. `_persist_upload(payload)`
   Purpose: Writes the uploaded file to `storage_dir/uploads`.

6. `_index_document_from_path(file_path, display_name, existing_summary=None, embedding_model=None)`
   Purpose: This is the main indexing function for one file.

7. `load_document(file_path)`
   File: `copilot_ui/loaders.py`
   Purpose: Detects the file type and dispatches to the correct ingestion loader.

8. One of the format-specific `.load(...)` methods runs:

| Loader | File | Purpose |
|---|---|---|
| `TextFileLoader.load()` | `rag_data_ingestion/text_loader.py` | Loads plain text files |
| `PDFLoader.load()` | `rag_data_ingestion/pdf_loader.py` | Extracts PDF text and metadata |
| `DocxLoader.load()` | `rag_data_ingestion/docx_loader.py` | Extracts DOCX content and optional tables |
| `ExcelLoader.load()` | `rag_data_ingestion/excel_loader.py` | Extracts sheet and row content |
| `JSONLoader.load()` | `rag_data_ingestion/json_loader.py` | Flattens JSON into searchable text |
| `CiscoConfigLoader.load()` | `rag_data_ingestion/cisco_loader.py` | Organizes Cisco config blocks |

9. `CleanDocument.from_ingested(ingested)`
   File: `rag_processing/models.py`
   Purpose: Converts raw ingestion output into the canonical processing model.

10. `DocumentPipeline.run(document)`
    File: `rag_processing/pipeline.py`
    Purpose: Runs the structure extractor, chunker, and metadata enricher.

11. `DocumentPipeline._ensure_domain_metadata(document)`
    Purpose: Adds `domain`, `domain_confidence`, and `domain_reason` if missing.

12. `DomainClassifier.classify_document(...)`
    File: `domain_routing/classifier.py`
    Purpose: Uses filename, metadata, content, and structural cues to classify documents into `general`, `legal`, `medical`, or `cisco`.

13. `DocumentPipeline._build_processors(document)`
    Purpose: Resolves the right extractor, chunker, and enricher from `ProcessorRegistry`.

14. `extractor.extract(document)`
    File: `rag_processing/extractors.py`
    Purpose: Converts raw text into a structured tree.

15. `chunker.chunk(structured_document)`
    File: `rag_processing/chunkers.py`
    Purpose: Converts the structure into chunks.

16. `enricher.enrich(chunks, structured_document)`
    File: `rag_processing/enrichers.py`
    Purpose: Adds `chunk_id`, `chunk_index`, `total_chunks`, and extra metadata.

17. `active_embedding_model.embed_documents([chunk.content for chunk in chunks])`
    File: `copilot_ui/embeddings.py`
    Purpose: Creates one embedding vector per chunk.

18. `build_stored_chunks(chunks, embeddings, ...)`
    File: `retrieval/services/builders.py`
    Purpose: Converts processing chunks into `StoredChunk` retrieval records.

19. `StoredChunk.from_processing_chunk(...)`
    File: `retrieval/models/records.py`
    Purpose: Normalizes chunk metadata into the retrieval schema.

20. `_rebuild_retrieval_service()`
    File: `copilot_ui/services.py`
    Purpose: Rebuilds the retrieval stack after new files are indexed.

21. `build_retrieval_service(records, query_embedder, config, chroma_path, collection_name)`
    File: `retrieval/services/builders.py`
    Purpose: Builds vector store, dense retriever, keyword retriever, hybrid retriever, reranker, and the final `RetrievalService`.

22. `ChromaVectorStore.replace_records(records)`
    File: `retrieval/retrievers/chroma_store.py`
    Purpose: Resets the Chroma collection and writes all records.

23. `KeywordRetriever._build_index()`
    File: `retrieval/retrievers/keyword.py`
    Purpose: Builds the lexical index on top of the stored chunk text and metadata.

24. `AppSnapshot.to_dict()`
    Purpose: Returns the new state to the browser.

### 6.3 Query-to-Answer Flow

1. `sendMessage()`
   File: `copilot_ui/static/app.js`
   Purpose: Reads the chat box, retrieval mode, selected domain, top-k, and source filters, then calls `/api/chat`.

2. `POST /api/chat`
   File: `copilot_ui/server.py`
   Purpose: Creates `QueryOptions` and forwards the query to the service layer.

3. `QueryOptions(...)`
   File: `copilot_ui/services.py`
   Purpose: Carries runtime query controls such as `mode`, `top_k`, `domain`, and `source_types`.

4. `CopilotApplicationService.ask(message, options)`
   Purpose: This is the main runtime function for chat answers.

5. `DomainRouter.route_query(query, manual_domain=None, available_domain_counts=None)`
   File: `domain_routing/router.py`
   Purpose: Decides whether the query should stay cross-domain or be filtered to one domain.

6. `DomainClassifier.classify_query(query, available_domains=...)`
   File: `domain_routing/classifier.py`
   Purpose: Scores the query using weighted lexical and structural signals.

7. `_build_filters(options, route_domain, apply_domain_filter)`
   File: `copilot_ui/services.py`
   Purpose: Produces `MetadataFilterSpec` for domain and source type filtering.

8. `RetrievalService.retrieve(request)`
   File: `retrieval/services/retrieval_service.py`
   Purpose: Orchestrates query normalization, embedding, retrieval, reranking, and result formatting.

9. `TechnicalQueryProcessor.process(query)`
   File: `retrieval/query_processing/processor.py`
   Purpose: Preserves technical terms, extracts quotes, creates keyword tokens, adds expansions, and infers structured hints.

10. `query_embedder.embed(processed_query)`
    Purpose: Produces the query embedding for dense or hybrid retrieval.

11. `_retrieve_candidates(...)`
    File: `retrieval/services/retrieval_service.py`
    Purpose: Chooses dense, keyword, or hybrid retrieval.

12. One of these retrieval strategies runs:

| Retriever | File | Purpose |
|---|---|---|
| `VectorRetriever.retrieve()` | `retrieval/retrievers/vector.py` | Dense similarity search |
| `KeywordRetriever.retrieve()` | `retrieval/retrievers/keyword.py` | BM25-like technical keyword search |
| `HybridRetriever.retrieve()` | `retrieval/retrievers/hybrid.py` | Fuses dense and keyword scores |

13. `ChromaVectorStore.search(query_embedding, top_k, filters)`
    File: `retrieval/retrievers/chroma_store.py`
    Purpose: Executes the dense vector lookup against Chroma.

14. `HeuristicReranker.rerank(query, candidates, top_k=...)`
    File: `retrieval/rerankers/heuristic.py`
    Purpose: Adds exact phrase, technical term, metadata, page, sheet, section, JSON path, and Cisco-specific boosts.

15. `_to_response_item(candidate)`
    File: `retrieval/services/retrieval_service.py`
    Purpose: Converts internal candidates into `RetrievedChunk` objects.

16. `answer_generator.generate(query, retrieval_response)`
    File: `copilot_ui/answers.py`
    Purpose: Creates the final answer and citations.

17. One of these answer generators runs:

| Generator | File | Purpose |
|---|---|---|
| `GroundedAnswerGenerator.generate()` | `copilot_ui/answers.py` | Extractive grounded answer from retrieved chunks |
| `OllamaAnswerGenerator.generate()` | `copilot_ui/answers.py` | LLM answer grounded in retrieved chunks |

18. `OllamaAnswerGenerator._build_prompt(...)`
    Purpose: Builds a domain-aware grounded prompt with labels, metadata, and chunk text.

19. `OllamaClient.chat(messages, temperature=0.1)`
    File: `copilot_ui/ollama.py`
    Purpose: Calls the local Ollama daemon to generate the final answer.

20. `ChatMessage(...)`
    File: `copilot_ui/models.py`
    Purpose: Wraps the assistant answer, citations, and metadata for the GUI.

21. `renderMessages()`
    File: `copilot_ui/static/app.js`
    Purpose: Renders the answer, source cards, retrieval metadata, and model/domain badges in the chat UI.

## 7. How Chunking Really Works

The current GUI uses:

```python
DocumentPipeline(max_size=900, overlap=120)
```

This is configured in `copilot_ui/services.py`.

Chunking rules depend on source type:

| Source type | Extractor behavior | Chunker behavior |
|---|---|---|
| `text`, `text_file` | Split into paragraphs | Group paragraphs into chunks |
| `pdf` | Split into pages, then page blocks | Chunk per page/block with page metadata |
| `docx` | Split into sections and paragraphs | Chunk per section |
| `web` | Split by detected headings and paragraphs | Chunk per section |
| `excel` | Split into sheets and rows | Chunk grouped rows with `row_start` and `row_end` |
| `json` | Build object tree by JSON path | Chunk by object subtree |
| `cisco`, `cisco_config` | Split by config blocks like `interface`, `router`, `policy-map` | Chunk by block |

The generic chunk assembly logic lives in `rag_processing/utils.py` inside `chunk_units(...)`.

## 8. API Route Map

| Route | Method | Frontend caller | Backend action |
|---|---|---|---|
| `/` | `GET` | Browser | Serve the GUI HTML |
| `/api/state` | `GET` | `fetchState()` | Return current app snapshot |
| `/api/health` | `GET` | Manual checks | Health probe |
| `/api/chroma/records` | `GET` | Manual checks | Inspect indexed chunks and embeddings |
| `/api/documents/upload` | `POST` | `uploadFiles()` | Load, process, embed, and index files |
| `/api/documents/remove` | `POST` | Remove button | Remove one indexed document |
| `/api/documents/clear` | `POST` | Clear docs button | Clear uploads and index |
| `/api/chat` | `POST` | `sendMessage()` | Run routing, retrieval, and answer generation |
| `/api/chat/reset` | `POST` | Clear chat button | Clear transcript |
| `/api/settings/ollama` | `POST` | `applyOllamaSettings()` | Change chat and embedding models |
| `/api/settings/ollama/refresh` | `POST` | `refreshOllamaModels()` | Refresh locally installed Ollama models |

## 9. Commands to Run the Main Functions

### 9.1 Launch the GUI

Preferred production-like command:

```bash
cd "$ROOT"
./run_copilot.sh
```

Show launcher help:

```bash
cd "$ROOT"
./run_copilot.sh --help
```

Dry run without launching:

```bash
cd "$ROOT"
COPILOT_DRY_RUN=1 ./run_copilot.sh
```

Direct Python launch:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" examples/9_launch_copilot_ui.py
```

Directly call `run_server(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from copilot_ui import run_server
run_server(host="127.0.0.1", port=8765, open_browser=False)
PY
```

### 9.2 Hit the GUI API Without the Browser

Get current state:

```bash
curl http://127.0.0.1:8765/api/state
```

Health check:

```bash
curl http://127.0.0.1:8765/api/health
```

Inspect indexed chunks in Chroma:

```bash
curl "http://127.0.0.1:8765/api/chroma/records?limit=5&offset=0&include_embeddings=0"
```

### 9.3 Run the Public Ingestion Functions

Important note:

The legacy `examples/1_*.py` through `examples/6_*.py` are useful for reading, but some of them still expect you to edit file paths before they become fully runnable in your environment.

Use the commands below as the reproducible commands for the real loader functions.

Run `TextFileLoader.load(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_data_ingestion import TextFileLoader
data = TextFileLoader().load("testing_files/txt/gibson.txt")
print(data.source.source_type)
print(data.content[:300])
PY
```

Run `PDFLoader.load(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_data_ingestion import PDFLoader
data = PDFLoader().load("testing_files/PDF/EvMateo.pdf", extract_metadata=True)
print(data.source.source_type)
print(data.source.metadata)
print(data.content[:300])
PY
```

Run `DocxLoader.load(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_data_ingestion import DocxLoader
data = DocxLoader().load("testing_files/Word/EvMateo.docx", extract_tables=True)
print(data.source.source_type)
print(data.content[:300])
PY
```

Run `ExcelLoader.load(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_data_ingestion import ExcelLoader
data = ExcelLoader().load("testing_files/Excel/ticket id testing excel.xlsx")
print(data.source.source_type)
print(data.source.metadata)
print(data.content[:300])
PY
```

Run `JSONLoader.load(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_data_ingestion import JSONLoader
data = JSONLoader().load("testing_files/JSON/jason testing file.json", flatten=True)
print(data.source.source_type)
print(data.content[:300])
PY
```

Run `CiscoConfigLoader.load(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_data_ingestion import CiscoConfigLoader
data = CiscoConfigLoader().load(
    "testing_files/Cisco/Cisco 3750.txt",
    organize_sections=True,
    redact_sensitive=True,
)
print(data.source.source_type)
print(data.content[:500])
PY
```

Run `load_document(file_path)` directly:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from copilot_ui.loaders import load_document
data = load_document("testing_files/txt/gibson.txt")
print(type(data).__name__)
print(data.source.source_type)
print(data.content[:300])
PY
```

Run `LoaderFactory.get_loader(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_data_ingestion import LoaderFactory
print(LoaderFactory.list_available_loaders())
print(LoaderFactory.get_loader("pdf"))
PY
```

Run `TextCleaner.clean(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_data_ingestion import TextCleaner
cleaner = TextCleaner()
print(cleaner.clean("Hello   world!!\n\n\nEmail me at a@b.com"))
PY
```

Run `chunk_text(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_data_ingestion import chunk_text
chunks = chunk_text("A" * 2500, chunk_size=1000, overlap=100)
print(len(chunks))
print([len(chunk) for chunk in chunks])
PY
```

### 9.4 Run the RAG Processing Pipeline

Run the processing tests:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" -m unittest tests.test_rag_processing
```

Run `DocumentPipeline.run(...)` directly:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_processing.models import CleanDocument
from rag_processing.pipeline import DocumentPipeline

doc = CleanDocument(
    document_id="demo-doc",
    source_type="text",
    source="memory://demo",
    content="Paragraph one.\n\nParagraph two with more detail.\n\nParagraph three.",
    metadata={},
)

pipeline = DocumentPipeline(max_size=200, overlap=20)
chunks = pipeline.run(doc)

for chunk in chunks:
    print(chunk.chunk_id, chunk.metadata.chunk_index, chunk.metadata.total_chunks)
    print(chunk.content)
    print("---")
PY
```

Run `DocumentPipeline.extract_structure(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from rag_processing.models import CleanDocument
from rag_processing.pipeline import DocumentPipeline

doc = CleanDocument(
    document_id="demo-doc",
    source_type="json",
    source="memory://json",
    content="user.name: Alice\nuser.role: admin\nitems[0].id: 10",
    metadata={},
)

structured = DocumentPipeline(max_size=200, overlap=20).extract_structure(doc)
print(structured.source_type)
print(structured.root.title)
print(len(structured.root.children))
PY
```

### 9.5 Run Embeddings and Indexing

Run `HashingEmbeddingModel.embed_documents(...)`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from copilot_ui.embeddings import HashingEmbeddingModel
model = HashingEmbeddingModel(dimension=32)
vectors = model.embed_documents(["router bgp 65001", "patient diagnosis plan"])
print(len(vectors), len(vectors[0]))
PY
```

Run `OllamaClient.list_models()`:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from copilot_ui.ollama import OllamaClient
client = OllamaClient.from_env()
print(client.list_models())
PY
```

Run `build_stored_chunks(...)` and `build_retrieval_service(...)` directly:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from copilot_ui.embeddings import HashingEmbeddingModel
from rag_processing import CleanDocument, DocumentPipeline
from rag_data_ingestion import TextFileLoader
from retrieval import RetrievalRequest, RetrievalMode
from retrieval.services import build_stored_chunks, build_retrieval_service

ingested = TextFileLoader().load("testing_files/txt/huracan.txt")
clean = CleanDocument.from_ingested(ingested)
chunks = DocumentPipeline(max_size=300, overlap=40).run(clean)

embedder = HashingEmbeddingModel(dimension=128)
embeddings = embedder.embed_documents([chunk.content for chunk in chunks])
records = build_stored_chunks(chunks, embeddings)

service = build_retrieval_service(
    records,
    query_embedder=embedder.as_query_embedder(),
    chroma_path="/tmp/nw_copilot_demo_chroma",
    collection_name="demo_chunks",
)

response = service.retrieve(
    RetrievalRequest(
        query="hurricane evacuation",
        mode=RetrievalMode.HYBRID,
        top_k=3,
        debug=True,
    )
)

for result in response.results:
    print(result.score, result.source_type, result.text[:160])
PY
```

### 9.6 Run Domain Routing

Run `DomainRouter.route_query(...)` directly:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
from domain_routing import DomainRouter
router = DomainRouter()
decision = router.route_query(
    "show me the switchport trunk configuration for GigabitEthernet1/0/24",
    available_domain_counts={"cisco": 3, "general": 2},
)
print(decision)
PY
```

Run the routing tests:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" -m unittest tests.test_domain_routing
```

### 9.7 Run Retrieval and Answer Generation Without the GUI

Run `CopilotApplicationService.add_uploaded_files(...)` and `ask(...)` directly:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
import base64
from copilot_ui.models import UploadedFilePayload
from copilot_ui.services import CopilotApplicationService, QueryOptions

service = CopilotApplicationService()

payload = UploadedFilePayload(
    name="notes.txt",
    content_base64=base64.b64encode(
        b"interface GigabitEthernet1/0/24\n switchport trunk allowed vlan 10,20,30"
    ).decode("utf-8"),
)

service.add_uploaded_files([payload])
state = service.ask("What VLANs are allowed on GigabitEthernet1/0/24?", QueryOptions(mode="hybrid", top_k=3))
print(state.messages[-1].content)
PY
```

Run copilot UI tests:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" -m unittest tests.test_copilot_ui
```

### 9.8 Inspect Chroma

Run the provided Chroma inspector:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" examples/10_inspect_chroma.py --limit 10
```

Include full embeddings:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" examples/10_inspect_chroma.py --limit 5 --include-embeddings
```

Direct Chroma access:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" - <<'PY'
import chromadb

client = chromadb.PersistentClient(path="/tmp/nw_copilot_ui/chroma")
collection = client.get_collection("nw_copilot_chunks")
rows = collection.get(limit=5, include=["documents", "metadatas", "embeddings"])
print(rows.keys())
print(rows["documents"][0][:300] if rows["documents"] else "No documents")
PY
```

### 9.9 Run the Main Verification Tests

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" -m unittest tests.test_rag_processing
"$PY" -m unittest tests.test_pdf_loader
"$PY" -m unittest tests.test_domain_routing
"$PY" -m unittest tests.test_copilot_ui
"$PY" -m unittest retrieval.tests.test_retrieval_pipeline
```

## 10. What Each Important Module Owns

| Module | Ownership |
|---|---|
| `copilot_ui/static/app.js` | Frontend actions, fetch calls, chat rendering, upload handling |
| `copilot_ui/server.py` | HTTP API and route handling |
| `copilot_ui/services.py` | Main backend orchestration and application state |
| `copilot_ui/loaders.py` | Loader dispatch by file type |
| `copilot_ui/embeddings.py` | Local hashing and Ollama embeddings |
| `copilot_ui/answers.py` | Grounded answer generation |
| `copilot_ui/ollama.py` | Thin client over Ollama HTTP API |
| `domain_routing/` | Domain classification and routing decisions |
| `rag_data_ingestion/` | File loading and text cleaning |
| `rag_processing/` | Structure extraction, chunking, metadata enrichment |
| `retrieval/` | Query processing, retrieval, fusion, reranking, result formatting |

## 11. Best Reading Order for New Engineers

1. `../run_copilot.sh`
2. `copilot_ui/server.py`
3. `copilot_ui/static/app.js`
4. `copilot_ui/services.py`
5. `copilot_ui/loaders.py`
6. `rag_processing/pipeline.py`
7. `rag_processing/extractors.py`
8. `rag_processing/chunkers.py`
9. `retrieval/services/builders.py`
10. `retrieval/services/retrieval_service.py`
11. `retrieval/retrievers/vector.py`
12. `retrieval/retrievers/keyword.py`
13. `retrieval/retrievers/hybrid.py`
14. `retrieval/rerankers/heuristic.py`
15. `copilot_ui/answers.py`
16. `copilot_ui/ollama.py`

## 12. Most Important Takeaways

1. The current GUI is a custom local web app, not Streamlit.
2. `CopilotApplicationService` is the center of the backend runtime.
3. Uploading a file triggers: load -> structure extraction -> chunking -> metadata enrichment -> embeddings -> Chroma indexing.
4. Asking a question triggers: domain routing -> query processing -> dense/keyword/hybrid retrieval -> reranking -> answer generation.
5. Chroma stores the final indexed chunks that retrieval uses.
6. The fastest way to inspect stored chunks is `examples/10_inspect_chroma.py`.
7. The fastest way to understand chunking behavior is `DocumentPipeline.run(...)`, not Chroma.

## 13. Suggested Onboarding Workshop for Junior Engineers

Session 1:

```bash
cd "$ROOT"
./run_copilot.sh
```

Goal: see the full app running.

Session 2:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" -m unittest tests.test_rag_processing
"$PY" -m unittest retrieval.tests.test_retrieval_pipeline
```

Goal: understand processing and retrieval without the GUI.

Session 3:

```bash
cd "$ROOT/nw_copilot_codespace"
"$PY" examples/10_inspect_chroma.py --limit 10
```

Goal: inspect exactly what the retrieval layer has indexed.

Session 4:

Read the following files in order:

1. `copilot_ui/services.py`
2. `rag_processing/pipeline.py`
3. `retrieval/services/retrieval_service.py`
4. `copilot_ui/answers.py`

Goal: understand the complete runtime path from user action to grounded answer.
