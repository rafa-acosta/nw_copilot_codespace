# Quick Reference Guide

## Getting Started

```bash
# Activate environment
source venv/bin/activate

# Run an example
python examples/1_text_loading.py
```

---

## 7 Loaders Available

| Loader | File Type | Usage |
|--------|-----------|-------|
| `TextFileLoader` | .txt | Plain text documents |
| `PDFLoader` | .pdf | PDF documents |
| `WebLoader` | URL | Web content |
| `DocxLoader` | .docx | Word documents |
| `ExcelLoader` | .xlsx | Excel spreadsheets |
| `JSONLoader` | .json | JSON files |
| `CiscoConfigLoader` | .conf/.cfg/.txt | Cisco configs |

---

## Basic Usage Pattern

```python
from rag_data_ingestion import [LoaderName]

# Create loader
loader = [LoaderName]()

# Load data
data = loader.load('file_path')

# Access results
print(data.content)          # Cleaned text
print(data.source.metadata)  # Source info
```

---

## Example: Load Each Format

```python
from rag_data_ingestion import (
    TextFileLoader, PDFLoader, WebLoader,
    DocxLoader, ExcelLoader, JSONLoader, CiscoConfigLoader
)

# Text
loader = TextFileLoader()
data = loader.load('file.txt')

# PDF
loader = PDFLoader()
data = loader.load('file.pdf')

# Web
loader = WebLoader()
data = loader.load('https://example.com')

# Word
loader = DocxLoader()
data = loader.load('file.docx')

# Excel
loader = ExcelLoader()
data = loader.load('file.xlsx')

# JSON
loader = JSONLoader()
data = loader.load('file.json')

# Cisco
loader = CiscoConfigLoader()
data = loader.load('config.txt')
```

---

## Text Cleaning Options

```python
from rag_data_ingestion import TextCleaner

# Default (good for general RAG)
cleaner = TextCleaner()

# Preserve structure (good for code)
cleaner = TextCleaner(
    lowercase=False,
    expand_contracs=False,
    remove_urls_flag=False,
)

# Aggressive (good for SEO)
cleaner = TextCleaner(
    lowercase=True,
    expand_contracs=True,
    remove_urls_flag=True,
    remove_emails_flag=True,
)

# Use with loader
loader = TextFileLoader(cleaner=cleaner)
data = loader.load('document.txt')
```

---

## Advanced: Factory Pattern

```python
from rag_data_ingestion import LoaderFactory

# Get loader dynamically
loader = LoaderFactory.get_loader('pdf')  # Returns PDFLoader

# List available types
types = LoaderFactory.list_available_loaders()
# Returns: ['text', 'pdf', 'url', 'docx', 'excel', 'json', 'cisco']

# Batch processing
files = [('doc1.txt', 'text'), ('doc2.pdf', 'pdf')]
for path, ftype in files:
    loader = LoaderFactory.get_loader(ftype)
    data = loader.load(path)
```

---

## Text Chunking for RAG

```python
from rag_data_ingestion import TextFileLoader, chunk_text

# Load
loader = TextFileLoader()
data = loader.load('document.txt')

# Chunk (1000 chars per chunk, 100 char overlap)
chunks = chunk_text(data.content, chunk_size=1000, overlap=100)

# Use chunks for embeddings
for chunk in chunks:
    # embedding = embedding_model.encode(chunk)
    pass
```

---

## FAQs

**Q: What's the difference between my cleaner settings?**  
A: `lowercase=True` makes searching case-insensitive. `remove_urls_flag=False` preserves links. See ARCHITECTURE.md for complete options.

**Q: How do I add a new file format?**  
A: Create a class extending `BaseDataLoader`, implement `load()` and `validate_source()`, register with `LoaderFactory`. See ARCHITECTURE.md "Extending the Library".

**Q: What happens on encoding errors?**  
A: UTF-8 fails → automatically tries Latin-1. No data loss.

**Q: Can I use this without RAG?**  
A: Yes! It's a general-purpose text extraction library. Just use the loaders and cleaners.

**Q: How do I handle very large files?**  
A: Current design loads into memory. For streaming, wrap loaders with `asyncio` or use generators. Future versions will support streaming.

---

## Key Files to Know

- **rag_data_ingestion/** - Main library
  - `__init__.py` - Public API
  - `base.py` - Abstract classes
  - `cleaning.py` - Text processing
  - `*_loader.py` - Format-specific loaders

- **examples/** - 7 working scenarios
  - Start with `1_text_loading.py`
  - See `6_advanced_usage.py` for patterns
  - Check `7_end_to_end_pipeline.py` for RAG workflow

- **Documentation**
  - `README.md` - Quick start
  - `ARCHITECTURE.md` - Deep dive
  - `IMPLEMENTATION_SUMMARY.md` - Project overview

---

## Common Errors & Solutions

**`ModuleNotFoundError: No module named 'rag_data_ingestion'`**  
→ Activate venv: `source venv/bin/activate`

**`ImportError: PyPDF2 is required...`**  
→ Install: `pip install PyPDF2==3.0.1`

**`FileNotFoundError: File not found`**  
→ Check file path exists and is correct

**`ValueError: Invalid [format] file`**  
→ File type mismatch (e.g., .pdf to TextFileLoader)

---

## Performance Tips

1. **Reuse loaders** - Create once, use multiple times
2. **Chunk smartly** - 500-2000 chars typical for embeddings
3. **Parallelize** - Use ThreadPoolExecutor for batch files
4. **Cache URLs** - Store web responses locally
5. **Monitor memory** - Very large files (>100MB) may need streaming

---

## Running Examples

```bash
# Activate venv
source venv/bin/activate

# Run individual examples
python examples/1_text_loading.py      # Text files
python examples/2_pdf_loading.py       # PDFs
python examples/3_web_loading.py       # Web URLs
python examples/4_office_documents.py  # DOCX, XLSX
python examples/5_json_and_config.py   # JSON, Cisco
python examples/6_advanced_usage.py    # Factory pattern
python examples/7_end_to_end_pipeline.py # Complete RAG
```

---

## Next Steps

1. ✅ **Understand:** Read README.md
2. ✅ **Explore:** Run examples
3. ✅ **Learn:** Review ARCHITECTURE.md
4. ✅ **Integrate:** Plug into your RAG system
5. ✅ **Extend:** Add custom loaders as needed

---

**Questions?** Check ARCHITECTURE.md or example files for detailed explanations.
