"""Loader selection helpers for the GUI application."""

from __future__ import annotations

from pathlib import Path
import re

from rag_data_ingestion import CiscoConfigLoader, DocxLoader, ExcelLoader, JSONLoader, PDFLoader, TextFileLoader
from rag_data_ingestion.base import IngestedData


CISCO_TEXT_HINTS = (
    re.compile(r"^\s*interface\s+\S+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*router\s+\S+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*hostname\s+\S+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*ip\s+access-list\s+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*line\s+vty\b", re.IGNORECASE | re.MULTILINE),
)


def is_probable_cisco_config(file_name: str, preview_text: str) -> bool:
    lowered_name = file_name.casefold()
    if any(term in lowered_name for term in ("cisco", "router", "switch", "firewall", "config")):
        return True
    return any(pattern.search(preview_text) for pattern in CISCO_TEXT_HINTS)


def load_document(file_path: str) -> IngestedData:
    """Load a supported document using the appropriate ingestion loader."""

    path = Path(file_path)
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        return PDFLoader().load(file_path, extract_metadata=True)
    if suffix == ".docx":
        return DocxLoader().load(file_path, extract_tables=True)
    if suffix in {".xlsx", ".xls"}:
        return ExcelLoader().load(file_path)
    if suffix == ".json":
        return JSONLoader().load(file_path, flatten=True)
    if suffix in {".cfg", ".conf", ".config"}:
        return CiscoConfigLoader().load(file_path, organize_sections=True, redact_sensitive=True)
    if suffix == ".txt":
        preview = path.read_text(encoding="utf-8", errors="ignore")[:8000]
        if is_probable_cisco_config(path.name, preview):
            return CiscoConfigLoader().load(file_path, organize_sections=True, redact_sensitive=True)
        return TextFileLoader().load(file_path)
    raise ValueError(f"Unsupported file type: {path.suffix or '[no extension]'}")
