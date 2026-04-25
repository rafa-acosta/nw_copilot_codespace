"""Structure extraction implementations for each supported source type."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .base import StructureExtractor
from .models import CleanDocument, StructuredDocument, StructuralNode
from .utils import split_paragraphs, split_lines, is_heading
from .models import _new_id


class TextStructureExtractor(StructureExtractor):
    def extract(self, document: CleanDocument) -> StructuredDocument:
        root = StructuralNode(node_id=_new_id(), node_type="document", title="Document")
        for idx, paragraph in enumerate(split_paragraphs(document.content), start=1):
            node = StructuralNode(
                node_id=_new_id(),
                node_type="paragraph",
                title=f"paragraph-{idx}",
                content=paragraph,
                path=["Document", f"paragraph-{idx}"],
            )
            root.add_child(node)
        return StructuredDocument(
            document_id=document.document_id,
            source_type=document.source_type,
            source=document.source,
            root=root,
            metadata=document.metadata,
        )


class PdfStructureExtractor(StructureExtractor):
    PAGE_RE = re.compile(r"^---\s*Page\s*(\d+)\s*---")

    def extract(self, document: CleanDocument) -> StructuredDocument:
        root = StructuralNode(node_id=_new_id(), node_type="document", title="PDF")
        lines = document.content.split("\n")
        current_page = None
        page_lines: List[str] = []

        def flush_page(page_number: int, page_content: List[str]) -> None:
            page_node = StructuralNode(
                node_id=_new_id(),
                node_type="page",
                title=f"page-{page_number}",
                metadata={"page": page_number},
                path=["PDF", f"page-{page_number}"],
            )
            for idx, paragraph in enumerate(split_paragraphs("\n".join(page_content)), start=1):
                block = StructuralNode(
                    node_id=_new_id(),
                    node_type="block",
                    title=f"block-{idx}",
                    content=paragraph,
                    metadata={"page": page_number},
                    path=["PDF", f"page-{page_number}", f"block-{idx}"],
                )
                page_node.add_child(block)
            root.add_child(page_node)

        for line in lines:
            match = self.PAGE_RE.match(line.strip())
            if match:
                if current_page is not None:
                    flush_page(current_page, page_lines)
                current_page = int(match.group(1))
                page_lines = []
                continue
            page_lines.append(line)

        if current_page is not None:
            flush_page(current_page, page_lines)
        else:
            # Fallback if page markers are missing
            page_node = StructuralNode(
                node_id=_new_id(),
                node_type="page",
                title="page-1",
                metadata={"page": 1},
                path=["PDF", "page-1"],
            )
            for idx, paragraph in enumerate(split_paragraphs(document.content), start=1):
                block = StructuralNode(
                    node_id=_new_id(),
                    node_type="block",
                    title=f"block-{idx}",
                    content=paragraph,
                    metadata={"page": 1},
                    path=["PDF", "page-1", f"block-{idx}"],
                )
                page_node.add_child(block)
            root.add_child(page_node)

        return StructuredDocument(
            document_id=document.document_id,
            source_type=document.source_type,
            source=document.source,
            root=root,
            metadata=document.metadata,
        )


class WebStructureExtractor(StructureExtractor):
    def extract(self, document: CleanDocument) -> StructuredDocument:
        root = StructuralNode(node_id=_new_id(), node_type="document", title="Web")
        lines = split_lines(document.content)
        current_section = StructuralNode(
            node_id=_new_id(),
            node_type="section",
            title="Introduction",
            path=["Web", "Introduction"],
        )

        def flush_section(section: StructuralNode) -> None:
            if section.children:
                root.add_child(section)

        for line in lines:
            if is_heading(line):
                flush_section(current_section)
                current_section = StructuralNode(
                    node_id=_new_id(),
                    node_type="section",
                    title=line,
                    path=["Web", line],
                )
                continue
            paragraph_node = StructuralNode(
                node_id=_new_id(),
                node_type="paragraph",
                title=None,
                content=line,
                path=["Web", current_section.title or "Section"],
            )
            current_section.add_child(paragraph_node)

        flush_section(current_section)

        return StructuredDocument(
            document_id=document.document_id,
            source_type=document.source_type,
            source=document.source,
            root=root,
            metadata=document.metadata,
        )


class DocxStructureExtractor(StructureExtractor):
    def extract(self, document: CleanDocument) -> StructuredDocument:
        root = StructuralNode(node_id=_new_id(), node_type="document", title="DOCX")
        lines = split_lines(document.content)
        current_section = StructuralNode(
            node_id=_new_id(),
            node_type="section",
            title="Document",
            path=["DOCX", "Document"],
        )

        def flush_section(section: StructuralNode) -> None:
            if section.children:
                root.add_child(section)

        for line in lines:
            if line.startswith("--- Table"):
                flush_section(current_section)
                current_section = StructuralNode(
                    node_id=_new_id(),
                    node_type="section",
                    title=line.strip("-").strip(),
                    path=["DOCX", line.strip("-").strip()],
                )
                continue
            if is_heading(line):
                flush_section(current_section)
                current_section = StructuralNode(
                    node_id=_new_id(),
                    node_type="section",
                    title=line,
                    path=["DOCX", line],
                )
                continue
            paragraph_node = StructuralNode(
                node_id=_new_id(),
                node_type="paragraph",
                content=line,
                path=["DOCX", current_section.title or "Section"],
            )
            current_section.add_child(paragraph_node)

        flush_section(current_section)

        return StructuredDocument(
            document_id=document.document_id,
            source_type=document.source_type,
            source=document.source,
            root=root,
            metadata=document.metadata,
        )


class ExcelStructureExtractor(StructureExtractor):
    SHEET_RE = re.compile(r"^---\s*Sheet:\s*(.+?)\s*---$")

    def extract(self, document: CleanDocument) -> StructuredDocument:
        root = StructuralNode(node_id=_new_id(), node_type="document", title="Excel")
        lines = document.content.split("\n")
        current_sheet = None
        row_idx = 0
        sheet_node: StructuralNode | None = None

        def flush_sheet(sheet: StructuralNode) -> None:
            if sheet.children:
                root.add_child(sheet)

        for line in lines:
            match = self.SHEET_RE.match(line.strip())
            if match:
                if sheet_node:
                    flush_sheet(sheet_node)
                current_sheet = match.group(1)
                sheet_node = StructuralNode(
                    node_id=_new_id(),
                    node_type="sheet",
                    title=current_sheet,
                    metadata={"sheet": current_sheet},
                    path=["Excel", current_sheet],
                )
                row_idx = 0
                continue
            if sheet_node is None:
                continue
            if not line.strip():
                continue
            row_idx += 1
            row_node = StructuralNode(
                node_id=_new_id(),
                node_type="row",
                content=line.strip(),
                metadata={"sheet": current_sheet, "row_index": row_idx},
                path=["Excel", current_sheet, f"row-{row_idx}"],
            )
            sheet_node.add_child(row_node)

        if sheet_node:
            flush_sheet(sheet_node)

        return StructuredDocument(
            document_id=document.document_id,
            source_type=document.source_type,
            source=document.source,
            root=root,
            metadata=document.metadata,
        )


class JsonStructureExtractor(StructureExtractor):
    def extract(self, document: CleanDocument) -> StructuredDocument:
        root = StructuralNode(node_id=_new_id(), node_type="document", title="JSON")
        lines = split_lines(document.content)
        tree: Dict[str, StructuralNode] = {}

        for line in lines:
            if ":" not in line:
                continue
            path, value = line.split(":", 1)
            path = path.strip()
            value = value.strip()
            segments = self._split_path(path)
            parent = root
            current_path = ["JSON"]
            for idx, segment in enumerate(segments, start=1):
                current_path.append(segment)
                key = "/".join(current_path)
                if key not in tree:
                    json_path = ".".join(segments[:idx])
                    node = StructuralNode(
                        node_id=_new_id(),
                        node_type="object",
                        title=segment,
                        path=current_path.copy(),
                        metadata={"json_path": json_path},
                    )
                    parent.add_child(node)
                    tree[key] = node
                parent = tree[key]
            leaf = StructuralNode(
                node_id=_new_id(),
                node_type="value",
                title=segments[-1],
                content=f"{path}: {value}",
                path=current_path + ["value"],
                metadata={"json_path": path},
            )
            parent.add_child(leaf)

        return StructuredDocument(
            document_id=document.document_id,
            source_type=document.source_type,
            source=document.source,
            root=root,
            metadata=document.metadata,
        )

    @staticmethod
    def _split_path(path: str) -> List[str]:
        segments: List[str] = []
        buffer = ""
        in_brackets = False
        for ch in path:
            if ch == "[":
                in_brackets = True
                buffer += ch
                continue
            if ch == "]":
                in_brackets = False
                buffer += ch
                continue
            if ch == "." and not in_brackets:
                if buffer:
                    segments.append(buffer)
                    buffer = ""
                continue
            buffer += ch
        if buffer:
            segments.append(buffer)
        return segments


class CiscoStructureExtractor(StructureExtractor):
    SECTION_MARKER_RE = re.compile(r"^---\s*Cisco Section:\s*(.+?)\s*---$", re.IGNORECASE)
    BLOCK_PATTERNS = [
        ("interface", re.compile(r"^interface\s+(\S+)", re.IGNORECASE)),
        ("router", re.compile(r"^router\s+(.+)", re.IGNORECASE)),
        ("access-list", re.compile(r"^ip\s+access-list\s+(standard|extended)\s+(\S+)", re.IGNORECASE)),
        ("class-map", re.compile(r"^class-map\s+(?:match-(any|all)\s+)?(\S+)", re.IGNORECASE)),
        ("policy-map", re.compile(r"^policy-map\s+(\S+)", re.IGNORECASE)),
        ("line", re.compile(r"^line\s+(\S+)(?:\s+(\S+))?", re.IGNORECASE)),
    ]

    def extract(self, document: CleanDocument) -> StructuredDocument:
        root = StructuralNode(node_id=_new_id(), node_type="document", title="Cisco")
        lines = document.content.split("\n")
        current_block: Tuple[str, str, List[str]] | None = None
        blocks: List[Tuple[str, str, List[str]]] = []

        def start_block(block_type: str, name: str) -> None:
            nonlocal current_block
            if current_block:
                blocks.append(current_block)
            current_block = (block_type, name, [])

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            section_match = self.SECTION_MARKER_RE.match(stripped)
            if section_match:
                if current_block:
                    blocks.append(current_block)
                    current_block = None
                continue
            matched = False
            for block_type, pattern in self.BLOCK_PATTERNS:
                match = pattern.match(stripped)
                if match:
                    name = " ".join([g for g in match.groups() if g]) if match.groups() else stripped
                    start_block(block_type, name)
                    current_block[2].append(stripped)
                    matched = True
                    break
            if not matched:
                if current_block is None:
                    start_block("global", "global")
                current_block[2].append(stripped)

        if current_block:
            blocks.append(current_block)

        for idx, (block_type, name, content_lines) in enumerate(blocks, start=1):
            block_node = StructuralNode(
                node_id=_new_id(),
                node_type="block",
                title=f"{block_type}:{name}",
                content="\n".join(content_lines).strip(),
                metadata={"block_type": block_type, "block_name": name},
                path=["Cisco", f"{block_type}:{name}", f"block-{idx}"],
            )
            root.add_child(block_node)

        return StructuredDocument(
            document_id=document.document_id,
            source_type=document.source_type,
            source=document.source,
            root=root,
            metadata=document.metadata,
        )
