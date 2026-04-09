"""Metadata filtering logic for retrieval candidates."""

from __future__ import annotations

from typing import Iterable

from retrieval.models import ChunkMetadata, MetadataFilterSpec, StoredChunk
from retrieval.utils import normalize_for_lookup


class MetadataFilter:
    """Applies declarative metadata constraints to chunk records."""

    def matches(self, metadata: ChunkMetadata, spec: MetadataFilterSpec | None) -> bool:
        if spec is None or spec.is_empty():
            return True

        for field_name, expected in spec.equals.items():
            if metadata.get(field_name) != expected:
                return False

        for field_name, expected_values in spec.any_of.items():
            if metadata.get(field_name) not in set(expected_values):
                return False

        for field_name, expected_substring in spec.contains.items():
            value = metadata.get(field_name)
            if value is None:
                return False
            if isinstance(value, (list, tuple, set)):
                expected = normalize_for_lookup(expected_substring)
                if not any(expected in normalize_for_lookup(str(item)) for item in value):
                    return False
                continue
            if normalize_for_lookup(expected_substring) not in normalize_for_lookup(str(value)):
                return False

        for field_name, numeric_range in spec.numeric_ranges.items():
            value = metadata.get(field_name)
            if not numeric_range.contains(value):
                return False

        if spec.tags_any and not set(metadata.tags).intersection(spec.tags_any):
            return False
        if spec.tags_all and not set(spec.tags_all).issubset(set(metadata.tags)):
            return False

        return True

    def apply(self, records: Iterable[StoredChunk], spec: MetadataFilterSpec | None) -> list[StoredChunk]:
        return [record for record in records if self.matches(record.metadata, spec)]
