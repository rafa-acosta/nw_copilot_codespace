# RAG Data Ingestion Library - Architecture & Design Guide

## Overview

A modular, scalable Python library for ingesting and preprocessing diverse data formats for Retrieval-Augmented Generation (RAG) systems. The library is designed with extensibility, maintainability, and RAG-specific preprocessing in mind.

---

## Architecture Overview

### Core Design Principles

1. **Modularity**: Each data format has its own loader module
2. **DRY (Don't Repeat Yourself)**: Shared utilities and base classes eliminate code duplication
3. **Low Coupling**: Loaders are independent; changes don't ripple across modules
4. **High Cohesion**: Related functionality is grouped together
5. **Extensibility**: Easy to add new data formats via the base class interface
6. **Programmatic Interface**: Designed as a backend library, not standalone scripts

### Module Structure

```
rag_data_ingestion/
├── __init__.py              # Package exports and factory registration
├── base.py                  # Abstract base class, data classes, factory
├── cleaning.py              # Text cleaning and normalization
├── utils.py                 # Utility functions (validation, chunking)
├── text_loader.py           # Plain text files
├── pdf_loader.py            # PDF documents
├── web_loader.py            # Web content (URLs)
├── docx_loader.py           # Microsoft Word documents
├── excel_loader.py          # Microsoft Excel files
├── json_loader.py           # JSON files
└── cisco_loader.py          # Cisco configuration files

examples/
├── 1_text_loading.py        # Text file examples
├── 2_pdf_loading.py         # PDF ingestion examples
├── 3_web_loading.py         # Web content examples
├── 4_office_documents.py    # Office formats examples
├── 5_json_and_config.py     # JSON and config examples
├── 6_advanced_usage.py      # Factory and batch processing
└── 7_end_to_end_pipeline.py # Complete RAG pipeline

rag_processing/
├── __init__.py              # Package exports
├── base.py                  # Abstract processor classes
├── models.py                # CleanDocument, Chunk, Metadata
├── utils.py                 # Chunking helpers
├── extractors.py            # Structure extractors
├── chunkers.py              # Semantic chunkers
├── enrichers.py             # Metadata enrichers
├── registry.py              # Processor registry
└── pipeline.py              # End-to-end pipeline
```

---

## Key Components

### 0. RAG Processing Layer (`rag_processing/`)

The processing layer operates **only on cleaned text** and provides the next stage in the pipeline:

**CleanDocument → StructuredDocument → Chunk → Metadata**

**Core abstractions:**
- `StructureExtractor` for source-specific structure detection
- `Chunker` for semantic chunking with size/overlap and fallback splitting
- `MetadataEnricher` for retrieval-ready metadata

**Per-source logic:**
- Text → paragraph + recursive chunking
- PDF → page/block chunking using page markers
- Web → section-aware chunking via heading heuristics
- DOCX → heading/table segmentation
- Excel → row-based chunking (no overlap)
- JSON → object-level chunking with JSON path preservation
- Cisco → regex block parsing (interface/router/ACL/class-map/policy-map/line)

**Registry:** `ProcessorRegistry` maps `source_type` → extractor/chunker/enricher.

### 1. Base Classes (`base.py`)

#### `IngestSource`
Metadata dataclass that captures:
- Source type (pdf, text, url, etc.)
- Source path/location
- Ingestion timestamp
- Additional metadata (headers, counts, etc.)

#### `IngestedData`
Result dataclass containing:
- Cleaned, normalized text content
- Source metadata
- Ready for downstream RAG processing

#### `BaseDataLoader` (Abstract)
Interface that all loaders implement:
```python
- load(source: str, **kwargs) -> IngestedData
  Load and preprocess data from a source
  
- validate_source(source: str) -> bool
  Validate source compatibility
  
- _create_ingest_source(...) -> IngestSource
  Helper to create metadata
```

#### `LoaderFactory`
Registry pattern for dynamic loader selection:
- `register()`: Register new loader types
- `get_loader()`: Get loader by type
- `list_available_loaders()`: Discover available types

**Why Factory Pattern?**
- Enables polymorphic loader usage
- Supports batch processing with dynamic type detection
- Allows late binding of loader implementation

### 2. Text Cleaning (`cleaning.py`)

#### Individual Functions
- `normalize_unicode()`: NFC normalization
- `remove_extra_whitespace()`: Collapse spaces, preserve structure
- `remove_special_characters()`: Sanitize text
- `convert_to_lowercase()`: Lowercase conversion
- `expand_contractions()`: American English contractions
- `remove_urls()`: Strip URLs
- `remove_emails()`: Strip email addresses

#### `TextCleaner` Class
Composable cleaner with configurable pipeline:
```python
cleaner = TextCleaner(
    normalize_unicode_chars=True,
    remove_extra_spaces=True,
    lowercase=False,
    expand_contracs=True,
    remove_urls_flag=True,
    remove_emails_flag=True,
)
cleaned = cleaner.clean(text)
```

**Design Decision**: Composition over inheritance allows flexible cleaning configurations per use case.

### 3. Utilities (`utils.py`)

#### File Validation
- `validate_file_exists()`: Check file presence
- `validate_file_extension()`: Verify allowed extensions

#### File I/O
- `read_file_safely()`: Smart encoding handling (UTF-8 fallback to Latin-1)
- `get_file_size()`: Get file size in bytes

#### Text Processing
- `sanitize_text()`: Remove problematic characters
- `chunk_text()`: Simple character-based chunking with overlap

**Why chunking utility?**
Provides basic chunking for RAG preparation. Production systems may use more sophisticated strategies (sentence/paragraph-aware chunking).

### 4. Loader Implementations

Each loader follows the same pattern:

1. **Inheritance**: Extends `BaseDataLoader`
2. **Initialization**: Takes optional `TextCleaner` instance
3. **Validation**: Implements `validate_source()`
4. **Loading**: Implements `load()` with format-specific extraction
5. **Metadata**: Captures format-specific info

#### Loader Examples

**TextFileLoader**
```python
loader = TextFileLoader()
data = loader.load('document.txt', encoding='utf-8')
```

**PDFLoader**
```python
loader = PDFLoader()
data = loader.load('document.pdf', extract_metadata=True)
```

**WebLoader**
```python
loader = WebLoader(timeout=10, verify_ssl=True)
data = loader.load('https://example.com', extract_links=True)
```

---

## Design Patterns Used

### 1. **Abstract Factory Pattern** (`BaseDataLoader`)
Defines interface for creating loaders; all concrete loaders extend this.

**Benefits**:
- Enforces consistent interface
- Enables polymorphic usage
- Easy to add new formats

### 2. **Factory Pattern** (`LoaderFactory`)
Centralized registry for loader registration and retrieval.

**Benefits**:
- Dynamic loader selection
- Plugin-like architecture
- Enables batch processing

### 3. **Strategy Pattern** (`TextCleaner`)
Composable cleaning operations for flexible preprocessing.

**Benefits**:
- Different cleaning for different use cases
- Reusable configuration
- Testable components

### 4. **Dataclass Pattern** (`IngestSource`, `IngestedData`)
Immutable data containers with type hints.

**Benefits**:
- Clear, self-documenting data structures
- Type safety
- Minimal boilerplate

---

## Dependency Management

### Required Dependencies
```
PyPDF2==3.16.0          # PDF extraction
beautifulsoup4==4.12.2  # HTML parsing
requests==2.31.0        # Web requests
python-docx==0.8.11     # DOCX parsing
openpyxl==3.10.10       # XLSX parsing
lxml==4.9.3             # XML/HTML parsing
```

### Dependency Strategy
- **Graceful Degradation**: Import errors caught at loader initialization with informative messages
- **Optional Deps**: Core utilities work without some libraries
- **Error Handling**: Missing libraries raise `ImportError` with installation instructions

---

## RAG Integration Points

### 1. Text Cleaning Pipeline
Removes noise and normalizes text for:
- Better embeddings
- Improved tokenization
- Reduced storage overhead

### 2. Metadata Preservation
Captures important context:
- Document source and type
- PDF page count and author
- Web response status and content-type
- Excel sheet information
- Configuration organization

### 3. Structured Output
`IngestedData` provides:
- Cleaned content ready for chunking
- Source metadata for tracking
- Timestamp for versioning

### 4. Chunking Support
`chunk_text()` utility enables:
- Character-based splitting
- Configurable overlap
- Pipeline-ready format

### Example End-to-End Flow
```
File Input
    ↓
[Loader] Extract raw content
    ↓
[TextCleaner] Normalize and clean
    ↓
[IngestedData] Structured output
    ↓
[chunk_text] Prepare for embeddings
    ↓
Vector Database
    ↓
RAG System
```

---

## Extensibility

### Adding a New Data Format

1. **Create new loader file**: `myformat_loader.py`

```python
from .base import BaseDataLoader, IngestedData
from .cleaning import TextCleaner

class MyFormatLoader(BaseDataLoader):
    SUPPORTED_EXTENSIONS = ['.myformat']
    
    def __init__(self, cleaner: Optional[TextCleaner] = None):
        self.cleaner = cleaner or TextCleaner()
    
    def validate_source(self, source: str) -> bool:
        # Implement validation
        return True
    
    def load(self, source: str, **kwargs) -> IngestedData:
        # Extract content
        raw_text = "..."
        
        # Clean
        cleaned_text = self.cleaner.clean(raw_text)
        
        # Return structured data
        ingest_source = self._create_ingest_source(
            source=source,
            source_type='myformat',
            metadata={}
        )
        return IngestedData(content=cleaned_text, source=ingest_source)
```

2. **Register in `__init__.py`**:
```python
from .myformat_loader import MyFormatLoader
LoaderFactory.register('myformat', MyFormatLoader)
```

3. **Add to exports**:
```python
__all__ = [
    # ... existing exports
    'MyFormatLoader',
]
```

---

## Error Handling Strategy

### Validation Errors
- **Invalid source**: Raised at `validate_source()`
- **Missing file**: `FileNotFoundError` with clear message
- **Invalid format**: `ValueError` with context

### Processing Errors
- **Encoding issues**: Auto-fallback to Latin-1
- **Malformed data**: Format-specific error with recovery hint
- **Missing dependencies**: `ImportError` with installation instructions

### Example
```python
try:
    loader = PDFLoader()
    data = loader.load('document.pdf')
except FileNotFoundError:
    logger.error(f"File not found: document.pdf")
except ValueError as e:
    logger.error(f"Invalid PDF: {str(e)}")
```

---

## Testing Strategy

### Unit Tests
Test individual components:
- Text cleaning functions
- File validation utilities
- Loader initialization

### Integration Tests
Test loader workflows:
- Load files of each format
- Validate metadata capture
- Check cleaning effectiveness

### Example Test
```python
def test_text_cleaner():
    cleaner = TextCleaner(lowercase=True)
    result = cleaner.clean("HELLO  World!!!")
    assert result == "hello world"

def test_pdf_loader():
    loader = PDFLoader()
    data = loader.load('test.pdf')
    assert len(data.content) > 0
    assert data.source.source_type == 'pdf'
```

---

## Performance Considerations

### Memory
- Streaming for large PDFs recommended in production
- In-memory processing suitable for documents < 100MB
- Consider lazy loading for very large Excel files

### Speed
- Typical processing times:
  - Plain text: < 100ms
  - PDFs: 100ms - 1s (varies with size)
  - Web content: 500ms - 5s (network dependent)
  - Office docs: 200ms - 1s

### Optimization Tips
1. Use appropriate chunk sizes (1000-2000 chars typical)
2. Enable caching for repeated URLs
3. Parallelize batch processing
4. Consider async/await for I/O-bound operations

---

## Security Considerations

### Input Validation
- File path validation prevents directory traversal
- URL validation for web loaders
- File extension whitelist enforcement

### Sensitive Data
- Cisco configs: Auto-redaction of passwords
- Email/passwords: Configurable removal
- PII: Consider masking in production

### Example
```python
loader = CiscoConfigLoader()
data = loader.load('config.txt', redact_sensitive=True)
# Passwords will be masked as [REDACTED]
```

---

## Best Practices

### For Library Users

1. **Reuse loader instances** when processing multiple files
2. **Configure cleaner once**, pass to loaders for consistency
3. **Use LoaderFactory** for dynamic type handling
4. **Implement retry logic** for web loaders
5. **Capture and log metadata** for tracking and debugging

### For Library Developers

1. **Keep loaders focused**: One purpose per loader
2. **Validate early**: Check source before processing
3. **Provide clear errors**: Include context and suggestions
4. **Document parameters**: Explain **kwargs options
5. **Write examples**: Every feature needs usage example

---

## Roadmap

### Planned Features
- [ ] Async loader support for I/O-bound operations
- [ ] Streaming for very large files
- [ ] More document formats (CSV, XML, Markdown)
- [ ] Language-specific cleaning (preserve code, URLs)
- [ ] Format detection from file content
- [ ] Caching layer for repeated ingestions
- [ ] Prometheus metrics
- [ ] Structured logging

### Performance Improvements
- [ ] Optional C-extensions for cleaning
- [ ] Parallel PDF page extraction
- [ ] Incremental loading for large files

---

## Contributing

### Adding a New Loader
1. Extend `BaseDataLoader`
2. Implement `load()` and `validate_source()`
3. Add comprehensive docstrings
4. Create examples showing usage
5. Add unit and integration tests

### Improving Cleaning
1. Add new functions to `cleaning.py`
2. Integrate into `TextCleaner` if widely useful
3. Document use cases and parameters
4. Include examples and benchmarks

---

## References

### Libraries Used
- **PyPDF2**: PDF text extraction
- **BeautifulSoup + requests**: Web scraping
- **python-docx**: Microsoft Word files
- **openpyxl**: Microsoft Excel files
- **lxml**: HTML/XML parsing

### Related Technologies
- **Embedding Models**: OpenAI, HuggingFace Transformers
- **Vector Databases**: Pinecone, Weaviate, Milvus
- **RAG Frameworks**: LangChain, LlamaIndex, Haystack
- **Chunking Strategies**: LangChain Text Splitters, Semantic Chunking

---

## License

[Specify your license here]

## Support

For issues or questions:
1. Check examples for usage patterns
2. Review docstrings for parameter details
3. Open an issue with reproducible example
