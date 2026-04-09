"""Text normalization and tokenization helpers for retrieval."""

from __future__ import annotations

import re
import unicodedata

from retrieval.models.query import QueryHints


IP_OR_CIDR_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b")
INTERFACE_PATTERN = re.compile(
    r"\b(?:GigabitEthernet|FastEthernet|TenGigabitEthernet|Loopback|Port-channel|Tunnel|Serial|Vlan|Gi|Fa|Te|Lo|Po)\S*\b",
    re.IGNORECASE,
)
JSON_PATH_PATTERN = re.compile(r"\b[A-Za-z_][\w-]*(?:\[[0-9]+\])?(?:\.[A-Za-z_][\w-]*(?:\[[0-9]+\])?)+\b")
ACL_OR_VLAN_PATTERN = re.compile(r"\b(?:acl|access-list|vlan)\s+[A-Za-z0-9_-]+\b", re.IGNORECASE)
QUOTED_PHRASE_PATTERN = re.compile(r'"([^"]+)"|\'([^\']+)\'')
TOKEN_PATTERN = re.compile(
    r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b"
    r"|\b(?:GigabitEthernet|FastEthernet|TenGigabitEthernet|Loopback|Port-channel|Tunnel|Serial|Vlan|Gi|Fa|Te|Lo|Po)\S*\b"
    r"|\b[A-Za-z_][\w-]*(?:\[[0-9]+\])?(?:\.[A-Za-z_][\w-]*(?:\[[0-9]+\])?)+\b"
    r"|\b[A-Za-z][A-Za-z0-9_./:-]*\b"
)
COMMAND_KEYWORDS = (
    "switchport",
    "spanning-tree",
    "ip access-list",
    "access-list",
    "router bgp",
    "router ospf",
    "router eigrp",
    "interface",
    "hostname",
    "snmp-server",
    "policy-map",
    "class-map",
    "service-policy",
    "ip route",
)


def unique_preserve_order(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return tuple(ordered)


def normalize_unicode(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_user_query(value: str, collapse: bool = True) -> str:
    normalized = normalize_unicode(value).strip()
    return collapse_whitespace(normalized) if collapse else normalized


def normalize_for_lookup(value: str) -> str:
    return collapse_whitespace(normalize_unicode(value).casefold())


def extract_quoted_phrases(value: str) -> tuple[str, ...]:
    phrases: list[str] = []
    for first, second in QUOTED_PHRASE_PATTERN.findall(value):
        phrase = first or second
        if phrase.strip():
            phrases.append(collapse_whitespace(phrase))
    return unique_preserve_order(phrases)


def tokenize_preserving_technical(value: str, minimum_length: int = 1) -> tuple[str, ...]:
    tokens = []
    for match in TOKEN_PATTERN.finditer(value):
        token = match.group(0).strip()
        if len(token) < minimum_length:
            continue
        tokens.append(normalize_for_lookup(token))
    return unique_preserve_order(tokens)


def extract_technical_terms(value: str) -> tuple[str, ...]:
    matches: list[str] = []
    for pattern in (IP_OR_CIDR_PATTERN, INTERFACE_PATTERN, JSON_PATH_PATTERN, ACL_OR_VLAN_PATTERN):
        matches.extend(match.group(0).strip() for match in pattern.finditer(value))

    normalized = normalize_user_query(value)
    lowered = normalized.casefold()
    if any(keyword in lowered for keyword in COMMAND_KEYWORDS):
        matches.append(normalized)

    for token in tokenize_preserving_technical(value):
        if any(character.isdigit() for character in token) or any(
            delimiter in token for delimiter in (".", "/", ":", "-", "[", "]")
        ):
            matches.append(token)
    return unique_preserve_order(matches)


def infer_query_hints(value: str, technical_terms: tuple[str, ...]) -> QueryHints:
    normalized = normalize_user_query(value)
    lowered = normalized.casefold()

    preferred_source_types: list[str] = []
    page_numbers = tuple(int(number) for number in re.findall(r"\bpage\s+(\d+)\b", lowered))
    sheet_names = tuple(
        collapse_whitespace(match)
        for match in re.findall(r"\bsheet\s+([A-Za-z0-9 _-]+)\b", normalized, flags=re.IGNORECASE)
    )
    section_terms = tuple(
        collapse_whitespace(match)
        for match in re.findall(r"\bsection\s+([A-Za-z0-9 _-]+)\b", normalized, flags=re.IGNORECASE)
    )
    json_paths = tuple(term for term in technical_terms if JSON_PATH_PATTERN.fullmatch(term))

    cisco_terms: list[str] = []
    if page_numbers:
        preferred_source_types.append("pdf")
    if "sheet" in lowered or "column" in lowered or "header" in lowered or "row" in lowered:
        preferred_source_types.append("excel")
    if json_paths or "json" in lowered or "key path" in lowered:
        preferred_source_types.append("json")
    if "section" in lowered or "heading" in lowered:
        preferred_source_types.append("docx")
    if any(keyword in lowered for keyword in COMMAND_KEYWORDS) or any(
        INTERFACE_PATTERN.fullmatch(term) or "vlan" in term.casefold() or "acl" in term.casefold()
        for term in technical_terms
    ):
        preferred_source_types.extend(("cisco", "cisco_config"))
        cisco_terms.extend(technical_terms)

    return QueryHints(
        preferred_source_types=unique_preserve_order(preferred_source_types),
        page_numbers=page_numbers,
        sheet_names=unique_preserve_order(list(sheet_names)),
        section_terms=unique_preserve_order(list(section_terms)),
        json_paths=unique_preserve_order(list(json_paths)),
        cisco_terms=unique_preserve_order(cisco_terms),
    )


def contains_term(haystack: str, needle: str) -> bool:
    normalized_haystack = normalize_for_lookup(haystack)
    normalized_needle = normalize_for_lookup(needle)
    if not normalized_needle:
        return False
    if any(delimiter in normalized_needle for delimiter in (".", "/", ":", "-", "[", "]")):
        return normalized_needle in normalized_haystack
    pattern = re.compile(rf"(?<!\w){re.escape(normalized_needle)}(?!\w)")
    return bool(pattern.search(normalized_haystack))


def extract_sheet_headers(text: str) -> tuple[str, ...]:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if "|" not in first_line:
        return ()
    headers = [collapse_whitespace(part) for part in first_line.split("|")]
    return unique_preserve_order([header for header in headers if header])
