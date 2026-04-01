"""Abstract base classes for structure extraction, chunking, and metadata enrichment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .models import CleanDocument, StructuredDocument, Chunk


class StructureExtractor(ABC):
    @abstractmethod
    def extract(self, document: CleanDocument) -> StructuredDocument:
        raise NotImplementedError


class Chunker(ABC):
    def __init__(self, max_size: int = 1000, overlap: int = 100):
        self.max_size = max_size
        self.overlap = overlap

    @abstractmethod
    def chunk(self, document: StructuredDocument) -> List[Chunk]:
        raise NotImplementedError


class MetadataEnricher(ABC):
    @abstractmethod
    def enrich(self, chunks: List[Chunk], document: StructuredDocument) -> List[Chunk]:
        raise NotImplementedError
