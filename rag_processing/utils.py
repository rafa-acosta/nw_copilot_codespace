"""Utility helpers for structure extraction and chunking."""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple


HEADING_MIN_LEN = 3
HEADING_MAX_LEN = 80


def split_lines(text: str) -> List[str]:
    return [line.strip() for line in text.split("\n") if line.strip()]


def split_paragraphs(text: str) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return paragraphs


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def is_heading(line: str) -> bool:
    if not line:
        return False
    if len(line) < HEADING_MIN_LEN or len(line) > HEADING_MAX_LEN:
        return False
    if line.endswith(":"):
        return True
    if line.isupper():
        return True
    words = line.split()
    if len(words) <= 1:
        return False
    title_like = sum(1 for w in words if w[:1].isupper()) / len(words)
    return title_like >= 0.6


def chunk_units(
    units: Iterable[str],
    max_size: int,
    overlap: int,
    delimiter: str = "\n\n",
    fallback_split: bool = True,
) -> List[str]:
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        chunk_text = delimiter.join(current).strip()
        if chunk_text:
            chunks.append(chunk_text)
        current = []
        current_len = 0

    for unit in units:
        if not unit:
            continue
        unit_len = len(unit)
        if unit_len > max_size and fallback_split:
            # flush current before splitting large unit
            flush()
            for sentence in split_sentences(unit):
                if len(sentence) <= max_size:
                    if current_len + len(sentence) + len(delimiter) > max_size and current:
                        flush()
                    current.append(sentence)
                    current_len += len(sentence) + len(delimiter)
                else:
                    # hard split for very long sentences
                    for i in range(0, len(sentence), max_size):
                        part = sentence[i:i + max_size]
                        if current_len + len(part) + len(delimiter) > max_size and current:
                            flush()
                        current.append(part)
                        current_len += len(part) + len(delimiter)
            flush()
            continue

        if current_len + unit_len + len(delimiter) > max_size and current:
            flush()
        current.append(unit)
        current_len += unit_len + len(delimiter)

    flush()

    if overlap > 0 and len(chunks) > 1:
        overlapped: List[str] = []
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                overlapped.append(chunk)
                continue
            prev = overlapped[-1]
            tail = prev[-overlap:] if len(prev) > overlap else prev
            overlapped.append(f"{tail}{delimiter}{chunk}".strip())
        return overlapped

    return chunks


def slice_lines_with_indices(lines: List[str], start: int, end: int) -> Tuple[str, int, int]:
    content = "\n".join(lines[start:end]).strip()
    return content, start + 1, end
