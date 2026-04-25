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
            tail = _overlap_tail(chunks[idx - 1], overlap, delimiter)
            overlapped.append(f"{tail}{delimiter}{chunk}".strip())
        return overlapped

    return chunks


def _overlap_tail(chunk: str, overlap: int, delimiter: str) -> str:
    if overlap <= 0 or len(chunk) <= overlap:
        return chunk

    units = [unit.strip() for unit in chunk.split(delimiter) if unit.strip()]
    if len(units) <= 1:
        return _trim_to_word_boundary(chunk, overlap)

    selected: List[str] = []
    selected_len = 0
    for unit in reversed(units):
        projected_len = selected_len + len(unit) + (len(delimiter) if selected else 0)
        if selected and projected_len > overlap:
            break
        if not selected and len(unit) > overlap:
            selected.append(_trim_to_word_boundary(unit, overlap))
            break
        selected.append(unit)
        selected_len = projected_len
    return delimiter.join(reversed(selected)).strip()


def _trim_to_word_boundary(text: str, max_chars: int) -> str:
    tail = text[-max_chars:].strip()
    if not tail:
        return ""
    first_space = tail.find(" ")
    if first_space > 0:
        tail = tail[first_space + 1 :].strip()
    return tail


def slice_lines_with_indices(lines: List[str], start: int, end: int) -> Tuple[str, int, int]:
    content = "\n".join(lines[start:end]).strip()
    return content, start + 1, end
