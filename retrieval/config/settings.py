"""Configuration models for the retrieval pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class QueryProcessingConfig:
    """Configuration for query normalization and analysis."""

    collapse_whitespace: bool = True
    casefold_for_keywords: bool = True
    enable_query_expansion: bool = False
    preserve_quoted_phrases: bool = True
    minimum_token_length: int = 2


@dataclass(slots=True)
class VectorRetrieverConfig:
    """Dense retrieval configuration."""

    top_k: int = 10
    candidate_pool_size: int = 40
    score_threshold: float | None = None
    similarity_metric: str = "cosine"


@dataclass(slots=True)
class KeywordRetrieverConfig:
    """Keyword retrieval configuration."""

    enabled: bool = True
    top_k: int = 15
    exact_phrase_boost: float = 2.5
    technical_term_boost: float = 1.4
    metadata_field_boost: float = 0.8
    minimum_token_length: int = 2


@dataclass(slots=True)
class HybridConfig:
    """Hybrid fusion configuration."""

    enabled: bool = True
    dense_weight: float = 0.65
    keyword_weight: float = 0.35
    fusion_strategy: str = "weighted_sum"
    reciprocal_rank_constant: int = 60
    candidate_pool_multiplier: int = 4


@dataclass(slots=True)
class SourceTypeProfile:
    """Per-source retrieval and reranking profile."""

    dense_weight: float
    keyword_weight: float
    metadata_weight: float
    exact_match_weight: float


def _default_source_profiles() -> dict[str, SourceTypeProfile]:
    return {
        "default": SourceTypeProfile(0.60, 0.40, 0.25, 0.20),
        "text": SourceTypeProfile(0.85, 0.15, 0.15, 0.10),
        "text_file": SourceTypeProfile(0.85, 0.15, 0.15, 0.10),
        "pdf": SourceTypeProfile(0.75, 0.25, 0.25, 0.18),
        "docx": SourceTypeProfile(0.70, 0.30, 0.30, 0.20),
        "web": SourceTypeProfile(0.72, 0.28, 0.22, 0.18),
        "excel": SourceTypeProfile(0.45, 0.55, 0.42, 0.32),
        "json": SourceTypeProfile(0.35, 0.65, 0.48, 0.36),
        "cisco": SourceTypeProfile(0.25, 0.75, 0.55, 0.45),
        "cisco_config": SourceTypeProfile(0.25, 0.75, 0.55, 0.45),
    }


@dataclass(slots=True)
class RerankerConfig:
    """Post-retrieval reranking configuration."""

    enabled: bool = True
    exact_phrase_boost: float = 0.70
    technical_term_boost: float = 0.18
    metadata_match_boost: float = 0.15
    source_hint_boost: float = 0.20
    page_match_boost: float = 0.28
    section_match_boost: float = 0.22
    sheet_match_boost: float = 0.30
    column_match_boost: float = 0.18
    json_path_boost: float = 0.35
    cisco_command_boost: float = 0.40


@dataclass(slots=True)
class ObservabilityConfig:
    """Logging and debugging configuration."""

    logger_name: str = "retrieval"
    log_level: str = "INFO"
    debug: bool = False


@dataclass(slots=True)
class RetrievalConfig:
    """Top-level retrieval configuration."""

    retrieval_mode: str = "hybrid"
    query_processing: QueryProcessingConfig = field(default_factory=QueryProcessingConfig)
    vector: VectorRetrieverConfig = field(default_factory=VectorRetrieverConfig)
    keyword: KeywordRetrieverConfig = field(default_factory=KeywordRetrieverConfig)
    hybrid: HybridConfig = field(default_factory=HybridConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    source_profiles: dict[str, SourceTypeProfile] = field(default_factory=_default_source_profiles)

    def profile_for(self, source_type: str) -> SourceTypeProfile:
        return self.source_profiles.get(source_type, self.source_profiles["default"])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RetrievalConfig":
        source_profiles_payload = payload.get("source_profiles", {})
        source_profiles = _default_source_profiles()
        for key, profile in source_profiles_payload.items():
            source_profiles[key] = SourceTypeProfile(**profile)

        return cls(
            retrieval_mode=str(payload.get("retrieval_mode", "hybrid")),
            query_processing=QueryProcessingConfig(**payload.get("query_processing", {})),
            vector=VectorRetrieverConfig(**payload.get("vector", {})),
            keyword=KeywordRetrieverConfig(**payload.get("keyword", {})),
            hybrid=HybridConfig(**payload.get("hybrid", {})),
            reranker=RerankerConfig(**payload.get("reranker", {})),
            observability=ObservabilityConfig(**payload.get("observability", {})),
            source_profiles=source_profiles,
        )

    @classmethod
    def from_json_file(cls, file_path: str | Path) -> "RetrievalConfig":
        with Path(file_path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return cls.from_dict(payload)
