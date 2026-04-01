"""
RAG processing pipeline: structure extraction, semantic chunking, metadata enrichment.
"""

from .models import (
    CleanDocument,
    StructuredDocument,
    StructuralNode,
    Chunk,
    Metadata,
)
from .base import StructureExtractor, Chunker, MetadataEnricher
from .pipeline import DocumentPipeline
from .registry import ProcessorRegistry
from .extractors import (
    TextStructureExtractor,
    PdfStructureExtractor,
    WebStructureExtractor,
    DocxStructureExtractor,
    ExcelStructureExtractor,
    JsonStructureExtractor,
    CiscoStructureExtractor,
)
from .chunkers import (
    TextChunker,
    PdfChunker,
    WebChunker,
    DocxChunker,
    ExcelChunker,
    JsonChunker,
    CiscoChunker,
)
from .enrichers import (
    DefaultMetadataEnricher,
    PdfMetadataEnricher,
    ExcelMetadataEnricher,
    JsonMetadataEnricher,
    CiscoMetadataEnricher,
)

__all__ = [
    "CleanDocument",
    "StructuredDocument",
    "StructuralNode",
    "Chunk",
    "Metadata",
    "StructureExtractor",
    "Chunker",
    "MetadataEnricher",
    "DocumentPipeline",
    "ProcessorRegistry",
    "TextStructureExtractor",
    "PdfStructureExtractor",
    "WebStructureExtractor",
    "DocxStructureExtractor",
    "ExcelStructureExtractor",
    "JsonStructureExtractor",
    "CiscoStructureExtractor",
    "TextChunker",
    "PdfChunker",
    "WebChunker",
    "DocxChunker",
    "ExcelChunker",
    "JsonChunker",
    "CiscoChunker",
    "DefaultMetadataEnricher",
    "PdfMetadataEnricher",
    "ExcelMetadataEnricher",
    "JsonMetadataEnricher",
    "CiscoMetadataEnricher",
]
