# Testing Guide: RAG Processing Pipeline

This guide explains how to validate the Structure Extractor → Chunker → Metadata Enricher pipeline.

## 1) Prerequisites
- Python 3.11+
- Dependencies installed (see requirements.txt)

## 2) What is being tested
The unit tests cover:
- Structure extraction by source type
- Semantic chunking behavior
- Metadata enrichment (IDs, indices, type-specific fields)

## 3) How to run the tests
From the workspace root:

```bash
python3 -m unittest tests/test_rag_processing.py
```

## 3.1) Test functions one by one

### A) Structure extractors only
Run a single extractor in isolation using a small in-memory document:

```bash
python3 - <<'PY'
from rag_processing.models import CleanDocument
from rag_processing.extractors import TextStructureExtractor

doc = CleanDocument(
	document_id="doc_text",
	source_type="text",
	source="memory://text",
	content="Para one.\n\nPara two.",
	metadata={},
)
structured = TextStructureExtractor().extract(doc)
print(len(structured.root.children))
print(structured.root.children[0].content)
PY
```

To test other extractors, replace `TextStructureExtractor` with:
- `PdfStructureExtractor`
- `WebStructureExtractor`
- `DocxStructureExtractor`
- `ExcelStructureExtractor`
- `JsonStructureExtractor`
- `CiscoStructureExtractor`

### B) Chunkers only
Run a chunker on a minimal structured document:

```bash
python3 - <<'PY'
from rag_processing.models import CleanDocument
from rag_processing.extractors import TextStructureExtractor
from rag_processing.chunkers import TextChunker

doc = CleanDocument(
	document_id="doc_text",
	source_type="text",
	source="memory://text",
	content="Para one.\n\nPara two with more content.",
	metadata={},
)
structured = TextStructureExtractor().extract(doc)
chunks = TextChunker(max_size=50, overlap=10).chunk(structured)
print(len(chunks))
print(chunks[0].content)
PY
```

To test other chunkers, replace `TextChunker` and the extractor accordingly:
- `PdfChunker` with `PdfStructureExtractor`
- `WebChunker` with `WebStructureExtractor`
- `DocxChunker` with `DocxStructureExtractor`
- `ExcelChunker` with `ExcelStructureExtractor`
- `JsonChunker` with `JsonStructureExtractor`
- `CiscoChunker` with `CiscoStructureExtractor`

### C) Metadata enrichers only
Run the enricher on existing chunks:

```bash
python3 - <<'PY'
from rag_processing.models import CleanDocument
from rag_processing.extractors import TextStructureExtractor
from rag_processing.chunkers import TextChunker
from rag_processing.enrichers import DefaultMetadataEnricher

doc = CleanDocument(
	document_id="doc_text",
	source_type="text",
	source="memory://text",
	content="Para one.\n\nPara two.",
	metadata={},
)
structured = TextStructureExtractor().extract(doc)
chunks = TextChunker(max_size=200, overlap=0).chunk(structured)
enriched = DefaultMetadataEnricher().enrich(chunks, structured)
print(enriched[0].metadata.chunk_id)
print(enriched[0].metadata.chunk_index, enriched[0].metadata.total_chunks)
PY
```

Use type-specific enrichers if needed:
- `PdfMetadataEnricher`
- `ExcelMetadataEnricher`
- `JsonMetadataEnricher`
- `CiscoMetadataEnricher`

## 4) Expected output
You should see a summary similar to:

```
.......
----------------------------------------------------------------------
Ran 7 tests in <time>s

OK
```

## 5) Test coverage overview
The test suite in tests/test_rag_processing.py validates:
- Text: paragraph-based chunking
- PDF: page/block chunking with page metadata
- Web: section-aware chunking with headings
- DOCX: heading-based segmentation
- Excel: row-based chunking without overlap
- JSON: object-level chunking with json_path
- Cisco: block parsing and block metadata

## 6) Troubleshooting
- Import errors: ensure you run tests from the workspace root.
- Missing dependencies: install required packages from requirements.txt.
- If a test fails, check the source_type mapping in rag_processing/registry.py.

## 7) Optional: Run all tests
If you add more tests later:

```bash
python3 -m unittest
```
