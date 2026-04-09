# RAG Data Ingestion Library

A modular, scalable Python library for ingesting and preprocessing diverse data formats for **Retrieval-Augmented Generation (RAG)** systems. 

Built with extensibility, maintainability, and best practices in mind.

---

## Features

✅ **Multiple Data Formats**
- Plain text files (.txt)
- PDF documents (.pdf)
- Web content (URLs)
- Microsoft Word (.docx)
- Microsoft Excel (.xlsx)
- JSON files (.json)
- Cisco network configurations (.conf, .cfg)

✅ **RAG-Optimized Processing**
- Text cleaning and normalization
- Unicode standardization
- URL/email removal (configurable)
- Contraction expansion
- Ready for chunking and embedding

✅ **RAG Processing Pipeline**
- Structure extraction
- Semantic chunking (size/overlap + fallback)
- Metadata enrichment optimized for retrieval

✅ **Production-Ready Design**
- Type hints on all functions
- Comprehensive error handling
- Detailed docstrings
- Factory pattern for extensibility
- Full test coverage examples

✅ **Modular Architecture**
- Low coupling, high cohesion
- DRY principles throughout
- Easy to extend with new formats
- Reusable utilities and base classes

---

## Quick Start

### 1. Install Dependencies

```bash
# Activate virtual environment
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 2. Basic Usage

```python
from rag_data_ingestion import TextFileLoader

# Load and clean a text file
loader = TextFileLoader()
data = loader.load('document.txt')

print(data.content)  # Cleaned text
print(data.source.metadata)  # Source info
```

### 2.1 RAG Processing Usage

```python
from rag_processing import CleanDocument, DocumentPipeline

clean_doc = CleanDocument(
    document_id="doc1",
    source_type="text",
    source="memory://text",
    content="Para one.\n\nPara two.",
    metadata={},
)

pipeline = DocumentPipeline(max_size=1200, overlap=150)
chunks = pipeline.run(clean_doc)
```

### 3. Different Data Formats

```python
from rag_data_ingestion import PDFLoader, WebLoader, DocxLoader

# Load PDF
pdf_loader = PDFLoader()
pdf_data = pdf_loader.load('document.pdf')

# Load from URL
web_loader = WebLoader()
web_data = web_loader.load('https://example.com')

# Load Word document
docx_loader = DocxLoader()
docx_data = docx_loader.load('document.docx')
```

---

## Documentation

See [ARCHITECTURE.md](ARCHITECTURE.md) for comprehensive architecture, design patterns, and technical details.

### Examples

Run examples to see the library in action:

```bash
python examples/1_text_loading.py
python examples/2_pdf_loading.py
python examples/3_web_loading.py
python examples/4_office_documents.py
python examples/5_json_and_config.py
python examples/6_advanced_usage.py
python examples/7_end_to_end_pipeline.py
```

### Local Copilot GUI with Ollama

The local GUI now expects Ollama for both embeddings and grounded answer generation.

```bash
ollama pull nomic-embed-text
ollama pull llama3.1:8b

ollama serve

export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_EMBED_MODEL=nomic-embed-text
export OLLAMA_CHAT_MODEL=llama3.1:8b

python examples/9_launch_copilot_ui.py
```

If you use different local models, set `OLLAMA_EMBED_MODEL` and `OLLAMA_CHAT_MODEL` before launching the GUI.
You can also change both models from the GUI itself through the new `Ollama Models` panel. Use `Refresh`
after pulling a new model, then apply the new chat or embedding model directly in the browser.

---

## API Reference

### TextFileLoader
```python
loader = TextFileLoader()
data = loader.load('file.txt', encoding='utf-8')
```

### PDFLoader
```python
loader = PDFLoader()
data = loader.load('file.pdf', extract_metadata=True)
```

### WebLoader
```python
loader = WebLoader(timeout=10, verify_ssl=True)
data = loader.load('https://example.com', extract_links=False)
```

### DocxLoader
```python
loader = DocxLoader()
data = loader.load('file.docx', extract_tables=True)
```

### ExcelLoader
```python
loader = ExcelLoader()
data = loader.load('file.xlsx', sheet_names=None)
```

### JSONLoader
```python
loader = JSONLoader()
data = loader.load('file.json', flatten=True)
```

### CiscoConfigLoader
```python
loader = CiscoConfigLoader()
data = loader.load('config.txt', organize_sections=True, redact_sensitive=True)
```

### TextCleaner
```python
from rag_data_ingestion import TextCleaner

cleaner = TextCleaner(
    normalize_unicode_chars=True,
    remove_extra_spaces=True,
    lowercase=False,
    expand_contracs=True,
    remove_urls_flag=True,
    remove_emails_flag=True,
    keep_punctuation=True,
)
cleaned = cleaner.clean(raw_text)
```

### LoaderFactory
```python
from rag_data_ingestion import LoaderFactory

loader = LoaderFactory.get_loader('pdf')
types = LoaderFactory.list_available_loaders()
```

---

## Project Structure

```
rag_data_ingestion/
├── __init__.py              # Package exports
├── base.py                  # Base classes and factory
├── cleaning.py              # Text cleaning & normalization
├── utils.py                 # Utility functions
├── text_loader.py           # Plain text files
├── pdf_loader.py            # PDF documents
├── web_loader.py            # Web content
├── docx_loader.py           # Word documents
├── excel_loader.py          # Excel files
├── json_loader.py           # JSON files
└── cisco_loader.py          # Cisco configurations

rag_processing/
├── __init__.py               # Package exports
├── base.py                   # Abstract processor classes
├── models.py                 # CleanDocument, Chunk, Metadata
├── utils.py                  # Chunking helpers
├── extractors.py             # Structure extractors
├── chunkers.py               # Semantic chunkers
├── enrichers.py              # Metadata enrichers
├── registry.py               # Processor registry
└── pipeline.py               # End-to-end pipeline

examples/
├── 1_text_loading.py        # Text examples
├── 2_pdf_loading.py         # PDF examples
├── 3_web_loading.py         # Web examples
├── 4_office_documents.py    # Office examples
├── 5_json_and_config.py     # JSON/Config examples
├── 6_advanced_usage.py      # Factory & batch patterns
└── 7_end_to_end_pipeline.py # Complete RAG workflow

tests/
└── test_rag_processing.py    # Processing pipeline tests

TESTING_GUIDE.md              # How to test rag_processing
```

---

## Advanced Usage

### Batch Processing
```python
from rag_data_ingestion import LoaderFactory

files = [
    ('doc1.txt', 'text'),
    ('doc2.pdf', 'pdf'),
    ('doc3.json', 'json'),
]

results = []
for file_path, file_type in files:
    loader = LoaderFactory.get_loader(file_type)
    data = loader.load(file_path)
    results.append(data)
```

### Unified Configuration
```python
from rag_data_ingestion import TextCleaner, PDFLoader, TextFileLoader

cleaner = TextCleaner(
    normalize_unicode_chars=True,
    remove_extra_spaces=True,
    lowercase=False,
)

pdf_loader = PDFLoader(cleaner=cleaner)
text_loader = TextFileLoader(cleaner=cleaner)
```

### RAG Pipeline Integration
```python
from rag_data_ingestion import TextFileLoader, chunk_text

loader = TextFileLoader()
data = loader.load('document.txt')

chunks = chunk_text(data.content, chunk_size=1000, overlap=100)
# Send chunks to embedding model...
# Store in vector database...
```

---

## Key Design Decisions

- **Modular Architecture**: Each format has independent loader
- **Factory Pattern**: Dynamic loader selection
- **Composable Cleaning**: Flexible text preprocessing
- **Type Hints**: Full typing support
- **Error Handling**: Graceful degradation with clear messages
- **RAG-Focused**: Output format optimized for embedding pipelines

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

---

## Error Handling

```python
from rag_data_ingestion import TextFileLoader

loader = TextFileLoader()

try:
    data = loader.load('nonexistent.txt')
except FileNotFoundError as e:
    print(f"File not found: {e}")
except ValueError as e:
    print(f"Invalid source: {e}")
```

---

## Performance Tips

1. Reuse loader instances for multiple files
2. Use appropriate chunk sizes (500-2000 chars typical)
3. Parallelize batch processing
4. Cache web responses
5. Consider streaming for very large files

---

## Installation & Setup

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run examples
python examples/1_text_loading.py
```

---

## Contributing

Contributions welcome! Please:
1. Follow existing code style
2. Add type hints to all functions
3. Include comprehensive docstrings
4. Add usage examples
5. Write tests for new features

---

## License

[Your License Here]

---

## Support

For questions or issues:
1. Check [ARCHITECTURE.md](ARCHITECTURE.md) for design details
2. Review example files for usage patterns
3. Check function docstrings for parameters
4. Open an issue with a minimal reproducible example

---

**Happy ingesting! 🚀**
