"""Metadata filter models for retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


ComparableValue = str | int | float | bool


@dataclass(slots=True)
class NumericRange:
    """Inclusive or exclusive numeric range for metadata filtering."""

    minimum: float | None = None
    maximum: float | None = None
    include_minimum: bool = True
    include_maximum: bool = True

    def contains(self, value: float | int | None) -> bool:
        if value is None:
            return False

        candidate = float(value)
        if self.minimum is not None:
            if self.include_minimum and candidate < self.minimum:
                return False
            if not self.include_minimum and candidate <= self.minimum:
                return False
        if self.maximum is not None:
            if self.include_maximum and candidate > self.maximum:
                return False
            if not self.include_maximum and candidate >= self.maximum:
                return False
        return True


@dataclass(slots=True)
class MetadataFilterSpec:
    """Declarative metadata filters applied during retrieval."""

    equals: Mapping[str, ComparableValue] = field(default_factory=dict)
    any_of: Mapping[str, Sequence[ComparableValue]] = field(default_factory=dict)
    contains: Mapping[str, str] = field(default_factory=dict)
    numeric_ranges: Mapping[str, NumericRange] = field(default_factory=dict)
    tags_any: Sequence[str] = field(default_factory=tuple)
    tags_all: Sequence[str] = field(default_factory=tuple)

    def is_empty(self) -> bool:
        return not any(
            (
                self.equals,
                self.any_of,
                self.contains,
                self.numeric_ranges,
                self.tags_any,
                self.tags_all,
            )
        )
