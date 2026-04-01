"""Data models for structure extraction, chunking, and metadata enrichment."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from rag_data_ingestion.base import IngestedData


def _new_id() -> str:
    return uuid4().hex


@dataclass
class CleanDocument:
    document_id: str
    source_type: str
    source: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_ingested(cls, ingested: "IngestedData") -> "CleanDocument":
        return cls(
            document_id=_new_id(),
            source_type=ingested.source.source_type,
            source=ingested.source.source_path,
            content=ingested.content,
            metadata=dict(ingested.source.metadata or {}),
        )


@dataclass
class StructuralNode:
    node_id: str
    node_type: str
    title: Optional[str] = None
    content: Optional[str] = None
    children: List["StructuralNode"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    path: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None

    def add_child(self, node: "StructuralNode") -> None:
        node.parent_id = self.node_id
        self.children.append(node)


@dataclass
class StructuredDocument:
    document_id: str
    source_type: str
    source: str
    root: StructuralNode
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Metadata:
    source_type: str
    source: str
    document_id: str
    chunk_id: str
    parent_section_id: Optional[str]
    chunk_index: int
    total_chunks: int
    structural_path: List[str]
    content_type: str
    page: Optional[int] = None
    sheet: Optional[str] = None
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    json_path: Optional[str] = None
    cisco_block_type: Optional[str] = None
    cisco_block_name: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    content: str
    metadata: Metadata
