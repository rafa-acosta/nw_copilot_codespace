"""Models for the local copilot GUI application."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utcnow_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO 8601 format."""

    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    """Create a stable-ish prefixed identifier for UI records."""

    return f"{prefix}_{uuid4().hex}"


@dataclass(slots=True)
class UploadedFilePayload:
    """Browser upload payload sent to the local server."""

    name: str
    content_base64: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UploadedFilePayload":
        name = str(payload.get("name", "")).strip()
        content_base64 = str(payload.get("content_base64", "")).strip()
        if not name:
            raise ValueError("Uploaded file name is required")
        if not content_base64:
            raise ValueError(f"Uploaded file '{name}' is empty")
        return cls(name=name, content_base64=content_base64)


@dataclass(slots=True)
class IndexedDocumentSummary:
    """Compact document summary rendered in the GUI sidebar."""

    document_id: str
    filename: str
    file_path: str
    source_type: str
    chunk_count: int
    added_at: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "source_type": self.source_type,
            "chunk_count": self.chunk_count,
            "added_at": self.added_at,
        }


@dataclass(slots=True)
class IndexedDocument:
    """Indexed document plus the retrieval chunk ids it owns."""

    summary: IndexedDocumentSummary
    chunk_ids: tuple[str, ...]
    temp_path: str


@dataclass(slots=True)
class ChatCitation:
    """Source citation attached to an assistant message."""

    chunk_id: str
    label: str
    source_type: str
    score: float
    excerpt: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "label": self.label,
            "source_type": self.source_type,
            "score": self.score,
            "excerpt": self.excerpt,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ChatMessage:
    """Message rendered in the chat transcript."""

    role: str
    content: str
    message_id: str = field(default_factory=lambda: new_id("msg"))
    created_at: str = field(default_factory=utcnow_iso)
    citations: tuple[ChatCitation, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "citations": [citation.to_dict() for citation in self.citations],
            "meta": dict(self.meta),
        }


@dataclass(slots=True)
class GeneratedAnswer:
    """Answer generator output consumed by the GUI service."""

    content: str
    citations: tuple[ChatCitation, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AppSnapshot:
    """Serialized application state sent to the frontend."""

    documents: tuple[IndexedDocumentSummary, ...]
    messages: tuple[ChatMessage, ...]
    retrieval_ready: bool
    chunk_count: int
    supported_types: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "documents": [document.to_dict() for document in self.documents],
            "messages": [message.to_dict() for message in self.messages],
            "retrieval_ready": self.retrieval_ready,
            "chunk_count": self.chunk_count,
            "supported_types": list(self.supported_types),
        }
