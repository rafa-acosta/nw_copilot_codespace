"""Query-time domain routing and manual override handling."""

from __future__ import annotations

from typing import Mapping

from .classifier import DomainClassifier
from .models import DomainDetectionResult, DomainRouteDecision, SUPPORTED_DOMAINS


class DomainRouter:
    """Resolves document and query domains for routing-aware RAG."""

    def __init__(
        self,
        *,
        classifier: DomainClassifier | None = None,
        auto_filter_threshold: float = 0.52,
    ) -> None:
        self.classifier = classifier or DomainClassifier()
        self.auto_filter_threshold = auto_filter_threshold

    def detect_document(
        self,
        *,
        source_type: str,
        file_path: str | None = None,
        content: str = "",
        metadata: Mapping[str, object] | None = None,
    ) -> DomainDetectionResult:
        return self.classifier.classify_document(
            source_type=source_type,
            file_path=file_path,
            content=content,
            metadata=metadata,
        )

    def route_query(
        self,
        query: str,
        *,
        manual_domain: str | None = None,
        available_domain_counts: Mapping[str, int] | None = None,
    ) -> DomainRouteDecision:
        counts = {
            domain: int(count)
            for domain, count in (available_domain_counts or {}).items()
            if domain in SUPPORTED_DOMAINS and int(count) > 0
        }
        available_domains = tuple(sorted(counts))

        if manual_domain:
            self.validate_domain(manual_domain)
            return DomainRouteDecision(
                domain=manual_domain,
                confidence=1.0,
                reason="manual override selected by the user",
                mode="manual",
                filter_applied=True,
            )

        detected = self.classifier.classify_query(query, available_domains=available_domains)
        filter_applied = detected.confidence >= self.auto_filter_threshold
        reason = detected.reason

        if available_domains and detected.domain not in counts:
            filter_applied = False
            reason = f"{reason}; no indexed {detected.domain} documents are available, so cross-domain retrieval stays enabled"
        elif available_domains and not filter_applied:
            reason = f"{reason}; confidence stayed below {self.auto_filter_threshold:.2f}, so cross-domain retrieval stays enabled"
        elif len(available_domains) == 1 and detected.domain in counts:
            only_domain = available_domains[0]
            detected = DomainDetectionResult(
                domain=only_domain,
                confidence=max(detected.confidence, 0.85),
                reason=f"{reason}; only {only_domain} documents are indexed",
                scores=detected.scores,
            )
            filter_applied = True

        return DomainRouteDecision(
            domain=detected.domain,
            confidence=detected.confidence,
            reason=reason,
            scores=detected.scores,
            mode="automatic",
            filter_applied=filter_applied,
        )

    @staticmethod
    def validate_domain(domain: str) -> None:
        if domain not in SUPPORTED_DOMAINS:
            supported = ", ".join(SUPPORTED_DOMAINS)
            raise ValueError(f"Unsupported domain '{domain}'. Expected one of: {supported}")
