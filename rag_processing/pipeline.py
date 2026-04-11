"""End-to-end document processing pipeline: clean -> structured -> chunked -> enriched."""

from __future__ import annotations

from typing import List, Optional, Type

from domain_routing import DomainClassifier

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
        domain_classifier: DomainClassifier | None = None,
    ) -> None:
        self.extractor = extractor
        self.chunker = chunker
        self.enricher = enricher
        self.max_size = max_size
        self.overlap = overlap
        self.domain_classifier = domain_classifier or DomainClassifier()

    def _ensure_domain_metadata(self, document: CleanDocument) -> None:
        if document.metadata.get("domain"):
            return

        detection = self.domain_classifier.classify_document(
            source_type=document.source_type,
            file_path=document.source,
            content=document.content,
            metadata=document.metadata,
        )
        document.metadata["domain"] = detection.domain
        document.metadata["domain_confidence"] = detection.confidence
        document.metadata["domain_reason"] = detection.reason

    def _build_processors(self, document: CleanDocument) -> tuple[StructureExtractor, Chunker, MetadataEnricher]:
        if self.extractor and self.chunker and self.enricher:
            return self.extractor, self.chunker, self.enricher

        extractor_cls, chunker_cls, enricher_cls = ProcessorRegistry.resolve(document.source_type)
        extractor = extractor_cls()
        chunker = chunker_cls(max_size=self.max_size, overlap=self.overlap)
        enricher = enricher_cls()
        return extractor, chunker, enricher

    def run(self, document: CleanDocument) -> List[Chunk]:
        self._ensure_domain_metadata(document)
        extractor, chunker, enricher = self._build_processors(document)
        structured = extractor.extract(document)
        chunks = chunker.chunk(structured)
        enriched = enricher.enrich(chunks, structured)
        return enriched

    def extract_structure(self, document: CleanDocument) -> StructuredDocument:
        self._ensure_domain_metadata(document)
        extractor, _, _ = self._build_processors(document)
        return extractor.extract(document)
