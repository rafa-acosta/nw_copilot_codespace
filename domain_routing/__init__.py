"""Reusable domain routing utilities for ingestion, retrieval, and prompting."""

from .classifier import DomainClassifier
from .models import DomainDetectionResult, DomainRouteDecision, SUPPORTED_DOMAINS
from .prompting import DomainPromptProfile, prompt_profile_for
from .router import DomainRouter

__all__ = [
    "DomainClassifier",
    "DomainDetectionResult",
    "DomainPromptProfile",
    "DomainRouteDecision",
    "DomainRouter",
    "SUPPORTED_DOMAINS",
    "prompt_profile_for",
]
