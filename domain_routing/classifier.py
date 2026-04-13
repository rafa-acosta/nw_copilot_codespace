"""Heuristic domain classification for document and query routing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, Mapping

from .models import DomainDetectionResult, SUPPORTED_DOMAINS


GENERAL_DOMAIN = "general"
GENERAL_BASE_SCORE = 1.0
SPECIALIST_BASE_SCORE = 0.25


def _normalize_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def _normalize_tokens(values: Iterable[str]) -> tuple[str, ...]:
    normalized = []
    seen: set[str] = set()
    for value in values:
        token = _normalize_token(value)
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class DomainSignalProfile:
    """Keyword and structural hints for a supported domain."""

    filename_terms: tuple[str, ...]
    metadata_terms: tuple[str, ...]
    content_terms: tuple[str, ...]
    strong_patterns: tuple[re.Pattern[str], ...]
    structural_patterns: tuple[re.Pattern[str], ...]


LEGAL_PROFILE = DomainSignalProfile(
    filename_terms=_normalize_tokens(
        (
            "legal",
            "agreement",
            "contract",
            "nda",
            "lease",
            "mortgage",
            "hipoteca",
            "policy",
            "complaint",
            "affidavit",
            "terms",
            "deed",
        )
    ),
    metadata_terms=_normalize_tokens(
        (
            "governing law",
            "effective date",
            "counterparty",
            "jurisdiction",
            "clause",
            "article",
            "section",
            "party",
            "parties",
        )
    ),
    content_terms=_normalize_tokens(
        (
            "whereas",
            "hereby",
            "herein",
            "hereto",
            "pursuant to",
            "governing law",
            "indemnify",
            "liability",
            "confidentiality",
            "breach",
            "termination",
            "plaintiff",
            "defendant",
            "notary",
            "contrato",
            "arrendamiento",
            "hipoteca",
            "escritura",
            "clause",
            "agreement",
        )
    ),
    strong_patterns=(
        re.compile(r"\bwhereas\b", re.IGNORECASE),
        re.compile(r"\bgoverning law\b", re.IGNORECASE),
        re.compile(r"\bthis (agreement|contract|lease)\b", re.IGNORECASE),
        re.compile(r"\bparty(?:ies)?\b.{0,30}\bshall\b", re.IGNORECASE),
    ),
    structural_patterns=(
        re.compile(r"^\s*(?:article|section|clause)\s+\d+[.:]?", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*\d+\.\d+\s+[A-Z].+$", re.MULTILINE),
        re.compile(r"^\s*IN WITNESS WHEREOF\b", re.IGNORECASE | re.MULTILINE),
    ),
)

MEDICAL_PROFILE = DomainSignalProfile(
    filename_terms=_normalize_tokens(
        (
            "medical",
            "clinical",
            "patient",
            "discharge",
            "diagnosis",
            "lab",
            "medication",
            "prescription",
            "soap",
            "radiology",
            "nursing",
            "hospital",
        )
    ),
    metadata_terms=_normalize_tokens(
        (
            "chief complaint",
            "assessment",
            "plan",
            "allergies",
            "vitals",
            "diagnosis",
            "medications",
            "encounter",
        )
    ),
    content_terms=_normalize_tokens(
        (
            "patient",
            "diagnosis",
            "assessment",
            "plan",
            "treatment",
            "medication",
            "dosage",
            "vital signs",
            "blood pressure",
            "heart rate",
            "chief complaint",
            "history of present illness",
            "allergies",
            "symptoms",
            "exam",
            "impression",
            "follow-up",
            "prescribed",
        )
    ),
    strong_patterns=(
        re.compile(r"\bchief complaint\b", re.IGNORECASE),
        re.compile(r"\bhistory of present illness\b", re.IGNORECASE),
        re.compile(r"\bassessment and plan\b", re.IGNORECASE),
        re.compile(r"\b(?:mg|mcg|mmhg|bpm|kg|lb|celsius|fahrenheit|ml)\b", re.IGNORECASE),
    ),
    structural_patterns=(
        re.compile(r"^\s*(?:assessment|plan|allergies|medications|diagnosis):", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*(?:bp|hr|rr|temp|spo2)\s*[:=]", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*(?:patient|dob|mrn)\s*[:=]", re.IGNORECASE | re.MULTILINE),
    ),
)

CISCO_PROFILE = DomainSignalProfile(
    filename_terms=_normalize_tokens(
        (
            "cisco",
            "router",
            "switch",
            "wireless",
            "wlc",
            "asa",
            "ios",
            "iosxe",
            "network",
            "vlan",
            "config",
        )
    ),
    metadata_terms=_normalize_tokens(
        (
            "interface",
            "router",
            "access-list",
            "policy-map",
            "class-map",
            "switchport",
            "wireless",
        )
    ),
    content_terms=_normalize_tokens(
        (
            "switchport",
            "spanning-tree",
            "interface",
            "router bgp",
            "router ospf",
            "ip access-list",
            "line vty",
            "snmp-server",
            "service-policy",
            "class-map",
            "policy-map",
            "hostname",
            "ssid",
            "wlan",
            "controller",
            "vlan",
        )
    ),
    strong_patterns=(
        re.compile(r"^\s*interface\s+\S+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*router\s+(?:bgp|ospf|eigrp)\b", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*switchport\s+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*line\s+vty\b", re.IGNORECASE | re.MULTILINE),
    ),
    structural_patterns=(
        re.compile(r"^\s*ip\s+access-list\s+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*snmp-server\s+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*wireless\b", re.IGNORECASE | re.MULTILINE),
        re.compile(r"\b(?:GigabitEthernet|FastEthernet|TenGigabitEthernet|Port-channel|Vlan)\S*\b", re.IGNORECASE),
    ),
)


DOMAIN_PROFILES: dict[str, DomainSignalProfile] = {
    "legal": LEGAL_PROFILE,
    "medical": MEDICAL_PROFILE,
    "cisco": CISCO_PROFILE,
}

SOURCE_TYPE_PRIORS: dict[str, dict[str, float]] = {
    "pdf": {"legal": 0.45, "medical": 0.45},
    "docx": {"legal": 0.45, "medical": 0.45},
    "excel": {"medical": 0.35, "legal": 0.25, "cisco": 0.15},
    "json": {"medical": 0.30, "legal": 0.20, "cisco": 0.35},
    "text": {"legal": 0.20, "medical": 0.20, "cisco": 0.20},
    "text_file": {"legal": 0.20, "medical": 0.20, "cisco": 0.20},
    "cisco": {"cisco": 4.50},
    "cisco_config": {"cisco": 4.75},
    "config": {"cisco": 4.25},
}


class DomainClassifier:
    """Weighted multi-signal domain classifier for ingestion and query routing."""

    def classify_document(
        self,
        *,
        source_type: str,
        file_path: str | None = None,
        content: str = "",
        metadata: Mapping[str, object] | None = None,
    ) -> DomainDetectionResult:
        return self._classify(
            source_type=source_type,
            file_path=file_path,
            content=content,
            metadata=metadata,
            classification_target="document",
        )

    def classify_query(
        self,
        query: str,
        *,
        available_domains: Iterable[str] | None = None,
    ) -> DomainDetectionResult:
        metadata = {}
        if available_domains:
            metadata["available_domains"] = list(available_domains)
        return self._classify(
            source_type="query",
            file_path=None,
            content=query,
            metadata=metadata,
            classification_target="query",
        )

    def _classify(
        self,
        *,
        source_type: str,
        file_path: str | None,
        content: str,
        metadata: Mapping[str, object] | None,
        classification_target: str,
    ) -> DomainDetectionResult:
        normalized_source_type = _normalize_token(source_type)
        file_name = self._resolve_file_name(file_path, metadata)
        metadata_blob = self._stringify_metadata(metadata)
        preview = content[:20000]

        base_scores = {
            domain: (GENERAL_BASE_SCORE if domain == GENERAL_DOMAIN else SPECIALIST_BASE_SCORE)
            for domain in SUPPORTED_DOMAINS
        }
        scores = dict(base_scores)
        reasons: dict[str, list[tuple[float, str]]] = {domain: [] for domain in SUPPORTED_DOMAINS}

        for domain, prior in SOURCE_TYPE_PRIORS.get(normalized_source_type, {}).items():
            scores[domain] += prior
            reasons[domain].append((prior, f"source type '{source_type}'"))

        if file_name:
            lowered_file_name = _normalize_token(file_name)
            for domain, profile in DOMAIN_PROFILES.items():
                matches = [term for term in profile.filename_terms if term in lowered_file_name]
                if matches:
                    weight = min(2.4, 1.10 + (0.45 * len(matches)))
                    scores[domain] += weight
                    reasons[domain].append((weight, f"filename matched {', '.join(matches[:3])}"))

        if metadata_blob:
            lowered_metadata = _normalize_token(metadata_blob)
            for domain, profile in DOMAIN_PROFILES.items():
                matches = [term for term in profile.metadata_terms if term in lowered_metadata]
                if matches:
                    weight = min(2.2, 0.80 + (0.35 * len(matches)))
                    scores[domain] += weight
                    reasons[domain].append((weight, f"metadata matched {', '.join(matches[:3])}"))

        lowered_preview = _normalize_token(preview)
        for domain, profile in DOMAIN_PROFILES.items():
            term_matches = [term for term in profile.content_terms if term in lowered_preview]
            if term_matches:
                weight = min(3.2, 0.55 + (0.28 * len(term_matches)))
                scores[domain] += weight
                reasons[domain].append((weight, f"content matched {', '.join(term_matches[:4])}"))

            strong_hits = sum(1 for pattern in profile.strong_patterns if pattern.search(preview))
            if strong_hits:
                weight = 1.40 * strong_hits
                scores[domain] += weight
                reasons[domain].append((weight, f"strong {classification_target} structure"))

            structural_hits = sum(1 for pattern in profile.structural_patterns if pattern.search(preview))
            if structural_hits:
                weight = min(2.4, 0.85 * structural_hits)
                scores[domain] += weight
                reasons[domain].append((weight, f"{classification_target} formatting cues"))

        selected_domain, confidence, reason = self._select_domain(
            scores=scores,
            base_scores=base_scores,
            reasons=reasons,
        )

        return DomainDetectionResult(
            domain=selected_domain,
            confidence=confidence,
            reason=reason,
            scores={domain: round(score, 4) for domain, score in scores.items()},
        )

    @staticmethod
    def _resolve_file_name(file_path: str | None, metadata: Mapping[str, object] | None) -> str:
        if metadata:
            filename = metadata.get("filename")
            if filename:
                return str(filename)
        if not file_path:
            return ""
        return Path(file_path).name

    @staticmethod
    def _stringify_metadata(metadata: Mapping[str, object] | None) -> str:
        if not metadata:
            return ""
        values: list[str] = []
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                values.append(f"{key} {' '.join(str(item) for item in value)}")
                continue
            values.append(f"{key} {value}")
        return " ".join(values)

    @staticmethod
    def _build_reason(
        domain: str,
        reasons: list[tuple[float, str]],
        winning_score: float,
        total_score: float,
    ) -> str:
        if not reasons:
            return f"defaulted to {domain} because no strong domain signals were found"

        ranked = sorted(reasons, key=lambda item: item[0], reverse=True)
        detail = "; ".join(text for _, text in ranked[:3])
        return f"{domain} selected from weighted signals ({detail}); score={winning_score:.2f}/{total_score:.2f}"

    def _select_domain(
        self,
        *,
        scores: Mapping[str, float],
        base_scores: Mapping[str, float],
        reasons: Mapping[str, list[tuple[float, str]]],
    ) -> tuple[str, float, str]:
        total_score = sum(scores.values()) or 1.0
        specialist_domains = tuple(DOMAIN_PROFILES)
        top_specialist = max(specialist_domains, key=scores.get)
        runner_up_specialist = max(
            (domain for domain in specialist_domains if domain != top_specialist),
            key=scores.get,
            default=top_specialist,
        )
        top_specialist_signal = scores[top_specialist] - base_scores[top_specialist]
        runner_up_signal = scores[runner_up_specialist] - base_scores[runner_up_specialist]
        specialist_margin = top_specialist_signal - runner_up_signal
        top_specialist_evidence = sum(
            1 for _, reason_text in reasons[top_specialist] if not reason_text.startswith("source type ")
        )

        if scores[GENERAL_DOMAIN] >= scores[top_specialist]:
            confidence = max(scores[GENERAL_DOMAIN] / total_score, 0.58)
            reason = self._build_general_reason(
                top_specialist=top_specialist,
                reasons=reasons[top_specialist],
                top_specialist_signal=top_specialist_signal,
                specialist_margin=specialist_margin,
                total_score=total_score,
                general_score=scores[GENERAL_DOMAIN],
                mode="baseline",
            )
            return GENERAL_DOMAIN, confidence, reason

        if top_specialist_signal < 1.05 and top_specialist_evidence < 2:
            confidence = max(scores[GENERAL_DOMAIN] / total_score, 0.56)
            reason = self._build_general_reason(
                top_specialist=top_specialist,
                reasons=reasons[top_specialist],
                top_specialist_signal=top_specialist_signal,
                specialist_margin=specialist_margin,
                total_score=total_score,
                general_score=scores[GENERAL_DOMAIN],
                mode="weak",
            )
            return GENERAL_DOMAIN, confidence, reason

        if specialist_margin < 0.35 and top_specialist_signal < 1.80:
            confidence = max(scores[GENERAL_DOMAIN] / total_score, 0.54)
            reason = self._build_general_reason(
                top_specialist=top_specialist,
                reasons=reasons[top_specialist],
                top_specialist_signal=top_specialist_signal,
                specialist_margin=specialist_margin,
                total_score=total_score,
                general_score=scores[GENERAL_DOMAIN],
                mode="ambiguous",
            )
            return GENERAL_DOMAIN, confidence, reason

        confidence = scores[top_specialist] / total_score
        reason = self._build_reason(top_specialist, reasons[top_specialist], scores[top_specialist], total_score)
        return top_specialist, confidence, reason

    @staticmethod
    def _build_general_reason(
        *,
        top_specialist: str,
        reasons: list[tuple[float, str]],
        top_specialist_signal: float,
        specialist_margin: float,
        total_score: float,
        general_score: float,
        mode: str,
    ) -> str:
        if not reasons:
            return (
                "general selected because no strong legal, medical, or cisco signals were found; "
                f"score={general_score:.2f}/{total_score:.2f}"
            )

        ranked = sorted(reasons, key=lambda item: item[0], reverse=True)
        detail = "; ".join(text for _, text in ranked[:3])
        if mode == "baseline":
            return (
                f"general selected because specialized signals did not outrank the general baseline "
                f"(strongest was {top_specialist}: {detail}); score={general_score:.2f}/{total_score:.2f}"
            )
        if mode == "weak":
            return (
                f"general selected because {top_specialist} signals stayed weak ({detail}); "
                f"specialist-signal={top_specialist_signal:.2f}"
            )
        return (
            f"general selected because specialized cues were ambiguous ({detail}); "
            f"specialist-margin={specialist_margin:.2f}"
        )
