"""End-to-end document processing pipeline: clean -> structured -> chunked -> enriched."""

from __future__ import annotations

from typing import List, Optional, Type

from .base import Chunker, MetadataEnricher, StructureExtractor
from .models import Chunk, CleanDocument, StructuredDocument
from .registry import ProcessorRegistry


class DocumentPipeline:
    def __init__(
        self,
        extractor: Optional[StructureExtractor] = None,
        chunker: Optional[Chunker] = None,
        enricher: Optional[MetadataEnricher] = None,
        max_size: int = 1000,
        overlap: int = 100,
    ) -> None:
        self.extractor = extractor
        self.chunker = chunker
        self.enricher = enricher
        self.max_size = max_size
        self.overlap = overlap

    def _build_processors(self, document: CleanDocument) -> tuple[StructureExtractor, Chunker, MetadataEnricher]:
        if self.extractor and self.chunker and self.enricher:
            return self.extractor, self.chunker, self.enricher

        extractor_cls, chunker_cls, enricher_cls = ProcessorRegistry.resolve(document.source_type)
        extractor = extractor_cls()
        chunker = chunker_cls(max_size=self.max_size, overlap=self.overlap)
        enricher = enricher_cls()
        return extractor, chunker, enricher

    def run(self, document: CleanDocument) -> List[Chunk]:
        extractor, chunker, enricher = self._build_processors(document)
        structured = extractor.extract(document)
        chunks = chunker.chunk(structured)
        enriched = enricher.enrich(chunks, structured)
        return enriched

    def extract_structure(self, document: CleanDocument) -> StructuredDocument:
        extractor, _, _ = self._build_processors(document)
        return extractor.extract(document)
