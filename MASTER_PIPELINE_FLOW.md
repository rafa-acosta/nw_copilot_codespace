# Master Pipeline Flow Guide

This document explains the **complete end-to-end pipeline** for the local RAG system in this repository.

It covers:

- ingestion
- cleaning
- structure extraction
- chunking
- metadata enrichment
- embeddings and storage handoff
- retrieval
- retrieval output handoff to answer generation

It also explains the **specific flow for each supported file type**:

- TXT
- PDF
- DOCX
- XLSX
- JSON
- Cisco configuration files

## 1. System Scope

The repository is split into three major layers:

### Ingestion Layer

Location:

- `rag_data_ingestion/`

Responsibility:

- open a source
- extract text
- normalize and clean the text
- preserve source-level metadata

Primary output:

- `IngestedData`

Main entry points:

- `rag_data_ingestion/text_loader.py`
- `rag_data_ingestion/pdf_loader.py`
- `rag_data_ingestion/docx_loader.py`
- `rag_data_ingestion/excel_loader.py`
- `rag_data_ingestion/json_loader.py`
- `rag_data_ingestion/cisco_loader.py`

### Processing Layer

Location:

- `rag_processing/`

Responsibility:

- convert cleaned text into source-aware structure
- split structure into chunks
- enrich chunks with retrieval-ready metadata

Primary output:

- `list[Chunk]`

Main entry points:

- `rag_processing/pipeline.py`
- `rag_processing/extractors.py`
- `rag_processing/chunkers.py`
- `rag_processing/enrichers.py`

### Retrieval Layer

Location:

- `retrieval/`

Responsibility:

- process user query
- embed query
- retrieve candidates
- apply metadata filters
- combine dense and keyword retrieval
- rerank candidates
- return structured retrieval output for answer generation

Primary output:

- `RetrievalResponse`

Main entry points:

- `retrieval/services/retrieval_service.py`
- `retrieval/retrievers/vector.py`
- `retrieval/retrievers/keyword.py`
- `retrieval/retrievers/hybrid.py`
- `retrieval/rerankers/heuristic.py`

## 2. The Complete Pipeline at a Glance

The full system flow is:

```text
Source File
  ->
Format-Specific Loader
  ->
Cleaned Text + Source Metadata
  ->
CleanDocument
  ->
Structure Extractor
  ->
StructuredDocument
  ->
Chunker
  ->
Chunks
  ->
Metadata Enricher
  ->
Retrieval-Ready Chunks
  ->
Embedding Model
  ->
Vector Store / Local Index
  ->
StoredChunk Records
  ->
User Query
  ->
Query Processor
  ->
Query Embedder
  ->
Dense Retrieval + Keyword Retrieval
  ->
Hybrid Fusion
  ->
Metadata Filtering
  ->
Reranking
  ->
RetrievalResponse
  ->
Answer Generation Layer
```

Important clarification:

- this repository now implements ingestion, processing, and retrieval
- the **final answer generation step** is still a downstream consumer of `RetrievalResponse`
- in other words, the pipeline is complete up to the point where a generator or local LLM consumes retrieved context

## 3. Core Data Contracts

The most important transitions in the system are:

### Stage 1: Raw Source to `IngestedData`

Defined in:

- `rag_data_ingestion/base.py`

Shape:

- `content`: cleaned text
- `source.source_type`
- `source.source_path`
- `source.timestamp`
- `source.metadata`

### Stage 2: `IngestedData` to `CleanDocument`

Defined in:

- `rag_processing/models.py`

Purpose:

- normalize the ingestion output into the processing contract

Shape:

- `document_id`
- `source_type`
- `source`
- `content`
- `metadata`

### Stage 3: `CleanDocument` to `StructuredDocument`

Defined in:

- `rag_processing/extractors.py`

Purpose:

- recover useful structure from cleaned text
- structure differs by source type

### Stage 4: `StructuredDocument` to `Chunk`

Defined in:

- `rag_processing/chunkers.py`

Purpose:

- create semantically useful retrieval units
- attach source-aware metadata

### Stage 5: `Chunk` to `StoredChunk`

Defined in:

- `retrieval/models/records.py`
- `retrieval/services/builders.py`

Purpose:

- attach embeddings
- normalize metadata into the retrieval schema

Canonical retrieval metadata fields:

- `document_id`
- `source_type`
- `file_path`
- `filename`
- `chunk_id`
- `page_number`
- `section`
- `sheet_name`
- `row_start`
- `row_end`
- `column_names`
- `json_key_path`
- `cisco_feature`
- `cisco_section`
- `tags`
- `structural_path`
- `custom`

### Stage 6: Query to `RetrievalResponse`

Defined in:

- `retrieval/models/query.py`
- `retrieval/models/results.py`
- `retrieval/services/retrieval_service.py`

Primary response fields:

- `original_query`
- `normalized_query`
- `retrieval_mode`
- `top_k_results`
- `results`
- `timings`
- `debug`

## 4. End-to-End Runtime Flow

This is the actual end-to-end execution order for a typical document.

### Step 1: Load the file

A format-specific loader validates the source and extracts text.

Examples:

- TXT uses `TextFileLoader`
- PDF uses `PDFLoader`
- DOCX uses `DocxLoader`
- XLSX uses `ExcelLoader`
- JSON uses `JSONLoader`
- Cisco config uses `CiscoConfigLoader`

Output:

- `IngestedData`

### Step 2: Clean and normalize text

The loader uses `TextCleaner` to:

- normalize Unicode
- collapse extra spaces
- optionally remove URLs and emails
- keep text suitable for downstream chunking and embedding

Important design note:

- cleaning happens **before** structure extraction
- this means structure extractors work on already normalized text

### Step 3: Convert to processing model

`CleanDocument.from_ingested(...)` converts ingestion output into the contract expected by `DocumentPipeline`.

Output:

- `CleanDocument`

### Step 4: Extract structure

`DocumentPipeline` resolves a source-specific extractor through `ProcessorRegistry`.

Examples:

- text -> paragraph nodes
- pdf -> page nodes and block nodes
- docx -> section nodes and paragraph nodes
- excel -> sheet nodes and row nodes
- json -> object/value tree with path preservation
- cisco -> configuration blocks such as `interface`, `router`, `access-list`, `policy-map`

Output:

- `StructuredDocument`

### Step 5: Chunk the structured content

The chunker creates retrieval-sized units.

Design principle:

- the chunking strategy depends on document structure, not just character count

Examples:

- PDF chunks stay page-aware
- DOCX chunks stay section-aware
- Excel chunks stay row-range-aware
- JSON chunks stay path-aware
- Cisco chunks stay block-aware

Output:

- `list[Chunk]`

### Step 6: Enrich chunk metadata

The metadata enricher populates:

- chunk identifiers
- chunk index
- total chunk count
- source type
- source path
- document id
- source-specific fields like page, sheet, JSON path, Cisco block type

Output:

- enriched `list[Chunk]`

### Step 7: Generate embeddings

This stage is external to the processing package and depends on your existing local embedding model.

Expected behavior:

- each chunk text is embedded using the same local embedding model used later for query embedding
- vector dimension must remain consistent across indexing and query-time retrieval

Output:

- `list[embedding vectors]`

### Step 8: Build retrieval records

`StoredChunk.from_processing_chunk(...)` or `build_stored_chunks(...)` converts processing chunks plus embeddings into retrieval records.

This is the point where retrieval-specific metadata becomes canonical.

Output:

- `list[StoredChunk]`

### Step 9: Store locally

Your existing local vector database stores:

- chunk text
- embedding
- metadata

The retrieval layer also supports an in-memory reference store through:

- `retrieval/retrievers/store.py`

### Step 10: Accept a user query

The retrieval pipeline starts with `RetrievalRequest`.

Optional controls:

- mode
- top_k
- score threshold
- metadata filters
- debug mode

### Step 11: Process the query

`TechnicalQueryProcessor`:

- normalizes whitespace and Unicode
- preserves technical tokens
- extracts quoted phrases
- extracts technical terms
- infers source-type hints

This is critical for:

- IP addresses
- interface names
- VLAN references
- ACL names
- JSON paths
- sheet names
- section references

### Step 12: Embed the query

`QueryEmbedder` generates the query vector.

The retrieval layer validates embedding dimensions before dense search.

### Step 13: Retrieve candidates

There are three supported modes:

- dense
- keyword
- hybrid

Dense retrieval:

- uses vector similarity
- best for semantic matches

Keyword retrieval:

- uses exact terms, phrases, technical tokens, and metadata values
- best for configuration lines, JSON paths, sheet names, headers, and exact commands

Hybrid retrieval:

- merges dense and keyword candidates
- weights them by source-type profile

### Step 14: Apply metadata filtering

Filters can constrain retrieval by:

- exact equality
- one-of match
- substring contains
- numeric range
- tags

Examples:

- only `source_type == "pdf"`
- only `sheet_name contains "Quarterly"`
- only `page_number == 12`
- only chunks tagged `network`

### Step 15: Rerank candidates

The heuristic reranker improves final ordering using:

- exact phrase boosts
- technical-token boosts
- metadata matches
- source-type hints
- page-aware boosts for PDFs
- section-aware boosts for DOCX
- sheet and column boosts for Excel
- JSON path boosts for JSON
- Cisco command boosts for configs

### Step 16: Return retrieval output

The final output is `RetrievalResponse`.

Each result includes:

- chunk text
- score
- metadata
- source type
- optional dense score
- optional keyword score
- optional rerank score
- matched terms
- applied boosts

### Step 17: Hand off to answer generation

The answer-generation layer should consume:

- the normalized query
- the retrieved chunks
- the metadata fields needed for citation or grounding

A downstream answer generator can:

- build a prompt
- generate citations
- cite page numbers for PDFs
- cite sections for DOCX
- cite sheets and row ranges for Excel
- cite JSON key paths
- cite Cisco features or interfaces

## 5. File-Type-Specific Pipeline Flows

This section explains the exact flow for each supported file type.

---

## 5.1 TXT Pipeline

### Input

- `.txt`

### Ingestion path

- `rag_data_ingestion/text_loader.py`

### Detailed flow

```text
TXT file
  ->
TextFileLoader.load()
  ->
raw file read
  ->
TextCleaner.clean()
  ->
IngestedData(content, source metadata)
  ->
CleanDocument.from_ingested()
  ->
TextStructureExtractor.extract()
  ->
paragraph nodes
  ->
TextChunker.chunk()
  ->
chunk_units()
  ->
DefaultMetadataEnricher.enrich()
  ->
Chunk list
  ->
chunk embedding
  ->
StoredChunk
  ->
dense or hybrid retrieval
  ->
RetrievalResponse
```

### Structure behavior

The text extractor treats the document as a sequence of paragraphs.

Why:

- plain text usually lacks reliable higher-level structure
- paragraph boundaries are often the best semantic units available

### Metadata behavior

Typical metadata:

- `document_id`
- `source_type = "text"` or `"text_file"`
- `file_path`
- `filename`
- `chunk_id`
- `structural_path`
- optional tags or custom metadata

### Retrieval behavior

Preferred style:

- semantic-heavy

Reason:

- text files often contain prose, notes, or freeform explanations
- dense similarity usually performs better than strict lexical matching

Keyword retrieval still helps when:

- filenames matter
- specific phrases must be matched
- tags or custom metadata matter

### Best answer-generation citation fields

- `filename`
- `chunk_id`
- `structural_path`

---

## 5.2 PDF Pipeline

### Input

- `.pdf`

### Ingestion path

- `rag_data_ingestion/pdf_loader.py`

### Detailed flow

```text
PDF file
  ->
PDFLoader.load()
  ->
PyPDF2 page extraction
  ->
"--- Page N ---" markers inserted
  ->
TextCleaner.clean()
  ->
IngestedData
  ->
CleanDocument.from_ingested()
  ->
PdfStructureExtractor.extract()
  ->
page nodes + block nodes
  ->
PdfChunker.chunk()
  ->
page-aware chunks
  ->
PdfMetadataEnricher.enrich()
  ->
Chunk list with page metadata
  ->
chunk embedding
  ->
StoredChunk(page_number preserved)
  ->
hybrid retrieval + page-aware reranking
  ->
RetrievalResponse
```

### Structure behavior

The PDF loader inserts page markers during extraction.

The PDF extractor uses those markers to reconstruct:

- page nodes
- paragraph or block nodes inside each page

Why this matters:

- retrieval can preserve page references
- citations can remain page-aware
- page-specific queries such as `page 12` can be boosted during reranking

### Metadata behavior

Typical metadata:

- `page_number`
- `pdf_title`
- `pdf_author`
- `page_count`
- `document_id`
- `chunk_id`

### Retrieval behavior

Preferred style:

- semantic-heavy with page-awareness

Reason:

- PDFs often contain long prose or report-like language
- but users also frequently ask for page-specific evidence

Important retrieval feature:

- page-aware reranking boosts candidates when the query explicitly references a page number

### Best answer-generation citation fields

- `filename`
- `page_number`
- `chunk_id`

---

## 5.3 DOCX Pipeline

### Input

- `.docx`

### Ingestion path

- `rag_data_ingestion/docx_loader.py`

### Detailed flow

```text
DOCX file
  ->
DocxLoader.load()
  ->
paragraph extraction + optional table extraction
  ->
"--- Table N ---" markers inserted
  ->
TextCleaner.clean()
  ->
IngestedData
  ->
CleanDocument.from_ingested()
  ->
DocxStructureExtractor.extract()
  ->
section nodes based on headings and table markers
  ->
DocxChunker.chunk()
  ->
section-aware chunks
  ->
DefaultMetadataEnricher.enrich()
  ->
Chunk list
  ->
chunk embedding
  ->
StoredChunk(section preserved where available)
  ->
hybrid retrieval + section-aware reranking
  ->
RetrievalResponse
```

### Structure behavior

DOCX content is treated as a more structured document than plain text.

The extractor uses:

- heading heuristics
- table markers

to break the document into sections.

Why:

- Word files often contain reports, SOPs, manuals, and structured narratives
- section-level chunking produces more coherent retrieval units than paragraph-only chunking

### Metadata behavior

Typical metadata:

- `paragraph_count`
- `table_count`
- `section`
- `structural_path`
- `document_id`
- `chunk_id`

### Retrieval behavior

Preferred style:

- balanced semantic + structure-aware

Reason:

- users frequently ask for named sections
- headings are meaningful retrieval signals

Important retrieval feature:

- section-aware reranking boosts chunks when the query mentions a section name

### Best answer-generation citation fields

- `filename`
- `section`
- `chunk_id`

---

## 5.4 XLSX Pipeline

### Input

- `.xlsx`

### Ingestion path

- `rag_data_ingestion/excel_loader.py`

### Detailed flow

```text
Excel file
  ->
ExcelLoader.load()
  ->
sheet traversal
  ->
"--- Sheet: NAME ---" markers inserted
  ->
rows converted to "A | B | C" text lines
  ->
TextCleaner.clean()
  ->
IngestedData
  ->
CleanDocument.from_ingested()
  ->
ExcelStructureExtractor.extract()
  ->
sheet nodes + row nodes
  ->
ExcelChunker.chunk()
  ->
row-range chunks
  ->
ExcelMetadataEnricher.enrich()
  ->
Chunk list with sheet, row_start, row_end
  ->
chunk embedding
  ->
StoredChunk(sheet and row range preserved)
  ->
hybrid retrieval with keyword-heavy weighting
  ->
RetrievalResponse
```

### Structure behavior

Excel is inherently tabular, so the system preserves:

- sheet boundaries
- row order
- row ranges

It does **not** use overlap the same way prose documents do, because:

- row integrity matters more than sentence continuity
- duplicate overlap can reduce precision in tables

### Metadata behavior

Typical metadata:

- `sheet_name`
- `row_start`
- `row_end`
- optional `column_names`
- `document_id`
- `chunk_id`

Important indexing note:

The current processing layer preserves sheet and row information directly.

If you want the retrieval layer to boost on column headers, the best practice is to pass `column_names` when building `StoredChunk` records. The example retrieval integration does exactly this for row chunks.

### Retrieval behavior

Preferred style:

- keyword-heavy hybrid

Reason:

- users often ask using exact column names, sheet names, statuses, IDs, or header labels
- semantic retrieval alone is usually weaker for spreadsheets than for prose

Important retrieval features:

- sheet-aware reranking
- column-aware boosts
- metadata filters on sheet name and row ranges

### Best answer-generation citation fields

- `filename`
- `sheet_name`
- `row_start`
- `row_end`
- `column_names`

---

## 5.5 JSON Pipeline

### Input

- `.json`

### Ingestion path

- `rag_data_ingestion/json_loader.py`

### Detailed flow

```text
JSON file
  ->
JSONLoader.load()
  ->
json parsing
  ->
optional flattening to "path: value" lines
  ->
TextCleaner.clean()
  ->
IngestedData
  ->
CleanDocument.from_ingested()
  ->
JsonStructureExtractor.extract()
  ->
object tree with json_path metadata
  ->
JsonChunker.chunk()
  ->
object-level chunks
  ->
JsonMetadataEnricher.enrich()
  ->
Chunk list with path metadata
  ->
chunk embedding
  ->
StoredChunk(json_key_path preserved)
  ->
hybrid retrieval with keyword-heavy weighting
  ->
RetrievalResponse
```

### Structure behavior

The loader can flatten JSON into readable `key.path: value` lines.

The extractor then reconstructs a tree using:

- dotted key paths
- bracketed list indexes

Why:

- this preserves machine-readable structure in a human-searchable format
- retrieval can then respond well to key-path-specific questions

### Metadata behavior

Typical metadata:

- `json_key_path`
- `json_type`
- `document_id`
- `chunk_id`

### Retrieval behavior

Preferred style:

- keyword-heavy hybrid

Reason:

- JSON questions often refer to exact keys or paths
- exact lexical matching on key paths is extremely important

Important retrieval features:

- technical-token-preserving query processing
- JSON path matching
- reranking boost when `json_key_path` matches a path-like query

### Best answer-generation citation fields

- `filename`
- `json_key_path`
- `chunk_id`

---

## 5.6 Cisco Configuration Pipeline

### Input

- `.cfg`
- `.conf`
- `.config`
- `.txt` when used as a config dump

### Ingestion path

- `rag_data_ingestion/cisco_loader.py`

### Detailed flow

```text
Cisco config file
  ->
CiscoConfigLoader.load()
  ->
raw text read
  ->
optional redaction of secrets and passwords
  ->
optional major-section organization
  ->
TextCleaner.clean()
  ->
IngestedData
  ->
CleanDocument.from_ingested()
  ->
CiscoStructureExtractor.extract()
  ->
regex-identified configuration blocks
  ->
CiscoChunker.chunk()
  ->
line-oriented block chunks
  ->
CiscoMetadataEnricher.enrich()
  ->
Chunk list with cisco block metadata
  ->
chunk embedding
  ->
StoredChunk(cisco_feature and cisco_section preserved)
  ->
hybrid retrieval with strong keyword preference
  ->
RetrievalResponse
```

### Structure behavior

Cisco configs are not prose documents. They are command hierarchies.

The extractor explicitly identifies blocks such as:

- `interface`
- `router`
- `access-list`
- `class-map`
- `policy-map`
- `line`
- fallback `global`

Why:

- configuration semantics are strongly tied to command context
- exact commands matter
- block-level grouping preserves local operational meaning

### Metadata behavior

Typical metadata:

- `cisco_feature`
- `cisco_section`
- `line_count`
- `section_count`
- `sections`
- `document_id`
- `chunk_id`

### Retrieval behavior

Preferred style:

- exact-match-friendly hybrid with strong keyword weighting

Reason:

- queries often contain exact commands
- interface names, VLANs, ACL names, and route statements must survive normalization
- lexical precision is often more important than paraphrase matching

Important retrieval features:

- technical query token preservation
- exact command phrase boosts
- Cisco-specific rerank boosts
- block-aware metadata

### Best answer-generation citation fields

- `filename`
- `cisco_feature`
- `cisco_section`
- `chunk_id`

## 6. Retrieval Strategy by Source Type

The retrieval layer intentionally uses different behavior depending on source type.

### TXT

- favor dense similarity
- use keyword signals as secondary support

### PDF

- favor dense similarity
- preserve and boost page metadata

### DOCX

- use balanced dense + keyword
- boost section-aware hits

### XLSX

- use keyword-heavy hybrid
- boost sheet names and column names

### JSON

- use keyword-heavy hybrid
- boost exact key paths and path-like tokens

### Cisco config

- use keyword-heavy hybrid
- boost exact commands, interface names, VLAN references, ACL names, and block metadata

## 7. Practical Integration Sequence

For a production end-to-end pipeline, the runtime sequence should be:

```python
ingested = loader.load(file_path)
clean_doc = CleanDocument.from_ingested(ingested)
chunks = DocumentPipeline(...).run(clean_doc)

# Existing local embedding/indexing layer
embeddings = embedding_model.embed_documents([chunk.content for chunk in chunks])
records = build_stored_chunks(chunks, embeddings, ...)
vector_store.upsert(records)

# Query-time retrieval
response = retrieval_service.retrieve(
    RetrievalRequest(
        query=user_query,
        top_k=5,
        mode=RetrievalMode.HYBRID,
    )
)

# Downstream answer generation
retrieved_context = response.results
```

Reference example:

- `examples/8_retrieval_pipeline.py`

## 8. What the Answer Generator Should Receive

The answer generator should not receive only plain text.

It should receive:

- the user query
- normalized query
- top retrieved chunks
- scores
- source metadata

Recommended answer-generation input fields:

- `result.text`
- `result.metadata["filename"]`
- `result.metadata["page_number"]`
- `result.metadata["section"]`
- `result.metadata["sheet_name"]`
- `result.metadata["row_start"]`
- `result.metadata["row_end"]`
- `result.metadata["json_key_path"]`
- `result.metadata["cisco_feature"]`
- `result.metadata["cisco_section"]`

This enables:

- grounded prompting
- citation building
- answer traceability
- source-aware formatting

## 9. Recommended Citation Style by File Type

### TXT

- filename + chunk id

### PDF

- filename + page number + chunk id

### DOCX

- filename + section + chunk id

### XLSX

- filename + sheet name + row range

### JSON

- filename + JSON key path

### Cisco config

- filename + feature + section/interface/block name

## 10. Summary

The complete pipeline in this repository works as a layered system:

1. ingestion converts files into normalized text plus source metadata
2. processing reconstructs source-aware structure and chunk boundaries
3. embedding and storage convert chunks into indexed retrieval records
4. retrieval converts a user query into ranked, metadata-rich context
5. answer generation consumes that context to produce grounded responses

The most important design rule across all file types is:

- **preserve the structure that matters for the source**

That means:

- paragraph semantics for TXT
- page semantics for PDF
- section semantics for DOCX
- sheet and row semantics for XLSX
- key-path semantics for JSON
- command/block semantics for Cisco configs

If this rule is preserved, retrieval quality and answer traceability stay strong even as the corpus grows.
