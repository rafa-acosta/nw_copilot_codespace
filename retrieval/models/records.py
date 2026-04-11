"""Stored chunk models used by the retrieval layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


JsonValue = str | int | float | bool | None | Mapping[str, Any] | Sequence[Any]


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(str(value) for value in values if value is not None and str(value).strip())


def _safe_filename(source: str | None) -> str | None:
    if not source:
        return None
    if "://" in source:
        return source.rsplit("/", maxsplit=1)[-1] or source
    return Path(source).name


def _get_nested(mapping: Mapping[str, Any], path: Sequence[str], default: Any = None) -> Any:
    current: Any = mapping
    for segment in path:
        if not isinstance(current, Mapping) or segment not in current:
            return default
        current = current[segment]
    return current


@dataclass(slots=True)
class ChunkMetadata:
    """Canonical metadata schema for retrieved chunks."""

    document_id: str
    source_type: str
    file_path: str | None = None
    filename: str | None = None
    chunk_id: str | None = None
    page_number: int | None = None
    section: str | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    column_names: tuple[str, ...] = ()
    json_key_path: str | None = None
    cisco_feature: str | None = None
    cisco_section: str | None = None
    domain: str | None = None
    domain_confidence: float | None = None
    domain_reason: str | None = None
    tags: tuple[str, ...] = ()
    structural_path: tuple[str, ...] = ()
    custom: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.filename = self.filename or _safe_filename(self.file_path)
        self.column_names = _as_tuple(self.column_names)
        self.tags = _as_tuple(self.tags)
        self.structural_path = _as_tuple(self.structural_path)

    def get(self, field_name: str, default: Any = None) -> Any:
        if field_name.startswith("custom."):
            return _get_nested(self.custom, field_name.split(".")[1:], default)
        if hasattr(self, field_name):
            return getattr(self, field_name)
        if field_name in self.custom:
            return self.custom[field_name]
        return default

    def searchable_values(self) -> tuple[str, ...]:
        values: list[str] = []
        for candidate in (
            self.filename,
            self.source_type,
            self.section,
            self.sheet_name,
            self.json_key_path,
            self.cisco_feature,
            self.cisco_section,
            self.domain,
        ):
            if candidate:
                values.append(candidate)
        values.extend(self.column_names)
        values.extend(self.tags)
        values.extend(self.structural_path)
        for value in self.custom.values():
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                values.extend(str(item) for item in value)
                continue
            values.append(str(value))
        return tuple(values)

    def as_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_type": self.source_type,
            "file_path": self.file_path,
            "filename": self.filename,
            "chunk_id": self.chunk_id,
            "page_number": self.page_number,
            "section": self.section,
            "sheet_name": self.sheet_name,
            "row_start": self.row_start,
            "row_end": self.row_end,
            "column_names": list(self.column_names),
            "json_key_path": self.json_key_path,
            "cisco_feature": self.cisco_feature,
            "cisco_section": self.cisco_section,
            "domain": self.domain,
            "domain_confidence": self.domain_confidence,
            "domain_reason": self.domain_reason,
            "tags": list(self.tags),
            "structural_path": list(self.structural_path),
            "custom": dict(self.custom),
        }


@dataclass(slots=True)
class StoredChunk:
    """Chunk plus embedding ready to be indexed and retrieved."""

    text: str
    embedding: tuple[float, ...]
    metadata: ChunkMetadata
    search_text: str | None = None

    def __post_init__(self) -> None:
        self.embedding = tuple(float(value) for value in self.embedding)
        if not self.embedding:
            raise ValueError("StoredChunk.embedding cannot be empty")
        if not self.metadata.chunk_id:
            raise ValueError("StoredChunk.metadata.chunk_id must be set")
        if self.search_text is None:
            searchable = " ".join(self.metadata.searchable_values())
            self.search_text = f"{self.text}\n{searchable}".strip()

    @classmethod
    def from_processing_chunk(
        cls,
        chunk: Any,
        embedding: Sequence[float],
        *,
        file_path: str | None = None,
        tags: Sequence[str] | None = None,
        custom_metadata: Mapping[str, JsonValue] | None = None,
        column_names: Sequence[str] | None = None,
    ) -> "StoredChunk":
        metadata = getattr(chunk, "metadata")
        source_path = file_path or getattr(metadata, "source", None)
        structural_path = tuple(getattr(metadata, "structural_path", []) or ())
        extra_metadata = dict(getattr(metadata, "extra", {}) or {})
        combined_custom = {**extra_metadata, **dict(custom_metadata or {})}
        domain = combined_custom.pop("domain", None)
        domain_confidence = combined_custom.pop("domain_confidence", None)
        domain_reason = combined_custom.pop("domain_reason", None)
        section = None
        if structural_path:
            source_type = getattr(metadata, "source_type", "") or ""
            if source_type in {"docx", "web"} and len(structural_path) >= 2:
                section = structural_path[1]
            elif source_type == "text" and len(structural_path) >= 1:
                section = structural_path[-1]

        return cls(
            text=getattr(chunk, "content"),
            embedding=tuple(float(value) for value in embedding),
            metadata=ChunkMetadata(
                document_id=getattr(metadata, "document_id"),
                source_type=getattr(metadata, "source_type"),
                file_path=source_path,
                filename=_safe_filename(source_path),
                chunk_id=getattr(metadata, "chunk_id"),
                page_number=getattr(metadata, "page", None),
                section=section,
                sheet_name=getattr(metadata, "sheet", None),
                row_start=getattr(metadata, "row_start", None),
                row_end=getattr(metadata, "row_end", None),
                column_names=_as_tuple(column_names),
                json_key_path=getattr(metadata, "json_path", None),
                cisco_feature=getattr(metadata, "cisco_block_type", None),
                cisco_section=getattr(metadata, "cisco_block_name", None),
                domain=str(domain) if domain is not None else None,
                domain_confidence=float(domain_confidence) if domain_confidence is not None else None,
                domain_reason=str(domain_reason) if domain_reason is not None else None,
                tags=_as_tuple(tags),
                structural_path=structural_path,
                custom=combined_custom,
            ),
        )


def infer_embedding_dimension(records: Iterable[StoredChunk]) -> int | None:
    """Infer vector size from the first record in a chunk collection."""

    for record in records:
        return len(record.embedding)
    return None
