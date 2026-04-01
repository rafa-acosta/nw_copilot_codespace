"""Metadata enrichers for chunks."""

from __future__ import annotations

from typing import List

from .base import MetadataEnricher
from .models import Chunk, StructuredDocument
from .models import _new_id


class DefaultMetadataEnricher(MetadataEnricher):
    def enrich(self, chunks: List[Chunk], document: StructuredDocument) -> List[Chunk]:
        total = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            chunk.metadata.source_type = document.source_type
            chunk.metadata.source = document.source
            chunk.metadata.document_id = document.document_id
            chunk.metadata.chunk_id = _new_id()
            chunk.metadata.chunk_index = idx
            chunk.metadata.total_chunks = total
            chunk.chunk_id = chunk.metadata.chunk_id
            chunk.document_id = document.document_id
        return chunks


class PdfMetadataEnricher(DefaultMetadataEnricher):
    pass


class ExcelMetadataEnricher(DefaultMetadataEnricher):
    pass


class JsonMetadataEnricher(DefaultMetadataEnricher):
    pass


class CiscoMetadataEnricher(DefaultMetadataEnricher):
    pass
