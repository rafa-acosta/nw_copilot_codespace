"""Chunking implementations for structured documents."""

from __future__ import annotations

from typing import List

from .base import Chunker
from .models import Chunk, Metadata, StructuredDocument, StructuralNode, _new_id
from .utils import chunk_units, split_lines


class TextChunker(Chunker):
    def chunk(self, document: StructuredDocument) -> List[Chunk]:
        paragraphs = [node.content for node in document.root.children if node.content]
        chunks_text = chunk_units(paragraphs, self.max_size, self.overlap)
        return self._build_chunks(document, chunks_text, document.root.node_id, ["Document"], "text")

    @staticmethod
    def _build_chunks(document: StructuredDocument, chunks_text: List[str], parent_id: str, path: List[str], content_type: str) -> List[Chunk]:
        return [
            Chunk(
                chunk_id=_new_id(),
                document_id=document.document_id,
                content=chunk_text,
                metadata=Metadata(
                    source_type=document.source_type,
                    source=document.source,
                    document_id=document.document_id,
                    chunk_id="",
                    parent_section_id=parent_id,
                    chunk_index=0,
                    total_chunks=0,
                    structural_path=path,
                    content_type=content_type,
                ),
            )
            for chunk_text in chunks_text
        ]


class WebChunker(Chunker):
    def chunk(self, document: StructuredDocument) -> List[Chunk]:
        chunks: List[Chunk] = []
        for section in document.root.children:
            paragraphs = [child.content for child in section.children if child.content]
            if not paragraphs:
                continue
            chunks_text = chunk_units(paragraphs, self.max_size, self.overlap)
            chunks.extend(
                TextChunker._build_chunks(document, chunks_text, section.node_id, section.path, "section")
            )
        return chunks


class DocxChunker(Chunker):
    def chunk(self, document: StructuredDocument) -> List[Chunk]:
        chunks: List[Chunk] = []
        for section in document.root.children:
            paragraphs = [child.content for child in section.children if child.content]
            if not paragraphs:
                continue
            chunks_text = chunk_units(paragraphs, self.max_size, self.overlap)
            chunks.extend(
                TextChunker._build_chunks(document, chunks_text, section.node_id, section.path, "section")
            )
        return chunks


class PdfChunker(Chunker):
    def chunk(self, document: StructuredDocument) -> List[Chunk]:
        chunks: List[Chunk] = []
        for page in document.root.children:
            blocks = [child.content for child in page.children if child.content]
            if not blocks:
                continue
            chunks_text = chunk_units(blocks, self.max_size, self.overlap)
            for chunk_text in chunks_text:
                chunks.append(
                    Chunk(
                        chunk_id=_new_id(),
                        document_id=document.document_id,
                        content=chunk_text,
                        metadata=Metadata(
                            source_type=document.source_type,
                            source=document.source,
                            document_id=document.document_id,
                            chunk_id="",
                            parent_section_id=page.node_id,
                            chunk_index=0,
                            total_chunks=0,
                            structural_path=page.path,
                            content_type="page",
                            page=page.metadata.get("page"),
                        ),
                    )
                )
        return chunks


class ExcelChunker(Chunker):
    def chunk(self, document: StructuredDocument) -> List[Chunk]:
        chunks: List[Chunk] = []
        for sheet in document.root.children:
            rows = [child for child in sheet.children if child.content]
            if not rows:
                continue
            current: List[str] = []
            start_row = None
            current_len = 0
            last_row = None
            for row in rows:
                row_text = row.content
                if row_text is None:
                    continue
                if current_len + len(row_text) + 2 > self.max_size and current:
                    chunk_text = "\n".join(current)
                    chunks.append(
                        Chunk(
                            chunk_id=_new_id(),
                            document_id=document.document_id,
                            content=chunk_text,
                            metadata=Metadata(
                                source_type=document.source_type,
                                source=document.source,
                                document_id=document.document_id,
                                chunk_id="",
                                parent_section_id=sheet.node_id,
                                chunk_index=0,
                                total_chunks=0,
                                structural_path=sheet.path,
                                content_type="row",
                                sheet=sheet.metadata.get("sheet"),
                                row_start=start_row,
                                row_end=last_row,
                            ),
                        )
                    )
                    current = []
                    current_len = 0
                    start_row = None
                if start_row is None:
                    start_row = row.metadata.get("row_index")
                current.append(row_text)
                current_len += len(row_text) + 2
                last_row = row.metadata.get("row_index")
            if current:
                chunks.append(
                    Chunk(
                        chunk_id=_new_id(),
                        document_id=document.document_id,
                        content="\n".join(current),
                        metadata=Metadata(
                            source_type=document.source_type,
                            source=document.source,
                            document_id=document.document_id,
                            chunk_id="",
                            parent_section_id=sheet.node_id,
                            chunk_index=0,
                            total_chunks=0,
                            structural_path=sheet.path,
                            content_type="row",
                            sheet=sheet.metadata.get("sheet"),
                            row_start=start_row,
                            row_end=last_row,
                        ),
                    )
                )
        return chunks


class JsonChunker(Chunker):
    def chunk(self, document: StructuredDocument) -> List[Chunk]:
        chunks: List[Chunk] = []
        for obj_node in document.root.children:
            lines = self._collect_lines(obj_node)
            chunks_text = chunk_units(lines, self.max_size, self.overlap, delimiter="\n", fallback_split=False)
            for chunk_text in chunks_text:
                chunks.append(
                    Chunk(
                        chunk_id=_new_id(),
                        document_id=document.document_id,
                        content=chunk_text,
                        metadata=Metadata(
                            source_type=document.source_type,
                            source=document.source,
                            document_id=document.document_id,
                            chunk_id="",
                            parent_section_id=obj_node.node_id,
                            chunk_index=0,
                            total_chunks=0,
                            structural_path=obj_node.path,
                            content_type="json_object",
                            json_path=obj_node.metadata.get("json_path") or obj_node.title,
                        ),
                    )
                )
        return chunks

    def _collect_lines(self, node: StructuralNode) -> List[str]:
        lines: List[str] = []
        if node.content:
            lines.append(node.content)
        for child in node.children:
            lines.extend(self._collect_lines(child))
        return lines


class CiscoChunker(Chunker):
    def chunk(self, document: StructuredDocument) -> List[Chunk]:
        chunks: List[Chunk] = []
        for block in document.root.children:
            if not block.content:
                continue
            lines = split_lines(block.content)
            chunks_text = chunk_units(lines, self.max_size, self.overlap, delimiter="\n")
            for chunk_text in chunks_text:
                chunks.append(
                    Chunk(
                        chunk_id=_new_id(),
                        document_id=document.document_id,
                        content=chunk_text,
                        metadata=Metadata(
                            source_type=document.source_type,
                            source=document.source,
                            document_id=document.document_id,
                            chunk_id="",
                            parent_section_id=block.node_id,
                            chunk_index=0,
                            total_chunks=0,
                            structural_path=block.path,
                            content_type="cisco_block",
                            cisco_block_type=block.metadata.get("block_type"),
                            cisco_block_name=block.metadata.get("block_name"),
                        ),
                    )
                )
        return chunks
