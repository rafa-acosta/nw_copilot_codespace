"""Processor registry for mapping source types to extractors, chunkers, and enrichers."""

from __future__ import annotations

from typing import Dict, Tuple, Type

from .base import StructureExtractor, Chunker, MetadataEnricher
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


class ProcessorRegistry:
    _registry: Dict[str, Tuple[Type[StructureExtractor], Type[Chunker], Type[MetadataEnricher]]] = {}

    @classmethod
    def register(
        cls,
        source_type: str,
        extractor: Type[StructureExtractor],
        chunker: Type[Chunker],
        enricher: Type[MetadataEnricher],
    ) -> None:
        cls._registry[source_type] = (extractor, chunker, enricher)

    @classmethod
    def resolve(
        cls, source_type: str
    ) -> Tuple[Type[StructureExtractor], Type[Chunker], Type[MetadataEnricher]]:
        if source_type not in cls._registry:
            raise ValueError(f"No processors registered for source_type '{source_type}'")
        return cls._registry[source_type]


ProcessorRegistry.register("text", TextStructureExtractor, TextChunker, DefaultMetadataEnricher)
ProcessorRegistry.register("text_file", TextStructureExtractor, TextChunker, DefaultMetadataEnricher)
ProcessorRegistry.register("pdf", PdfStructureExtractor, PdfChunker, PdfMetadataEnricher)
ProcessorRegistry.register("url", WebStructureExtractor, WebChunker, DefaultMetadataEnricher)
ProcessorRegistry.register("web", WebStructureExtractor, WebChunker, DefaultMetadataEnricher)
ProcessorRegistry.register("docx", DocxStructureExtractor, DocxChunker, DefaultMetadataEnricher)
ProcessorRegistry.register("excel", ExcelStructureExtractor, ExcelChunker, ExcelMetadataEnricher)
ProcessorRegistry.register("json", JsonStructureExtractor, JsonChunker, JsonMetadataEnricher)
ProcessorRegistry.register("cisco", CiscoStructureExtractor, CiscoChunker, CiscoMetadataEnricher)
ProcessorRegistry.register("cisco_config", CiscoStructureExtractor, CiscoChunker, CiscoMetadataEnricher)
