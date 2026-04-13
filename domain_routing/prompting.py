"""Domain-aware prompting profiles used during grounded answer generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainPromptProfile:
    """Prompt profile for a routed domain."""

    system_instruction: str
    response_instruction: str


PROMPT_PROFILES: dict[str, DomainPromptProfile] = {
    "general": DomainPromptProfile(
        system_instruction=(
            "Treat the context as general-purpose material. Stay grounded in the retrieved text and avoid assuming "
            "that the document is legal, medical, or networking content unless the context explicitly shows that."
        ),
        response_instruction=(
            "Prefer plain, precise wording and call out when the retrieved context is incomplete instead of inferring "
            "specialized meaning."
        ),
    ),
    "legal": DomainPromptProfile(
        system_instruction=(
            "Treat the context as legal material. Preserve clause intent precisely, distinguish obligations from "
            "definitions, and call out parties, dates, governing-law language, exceptions, and missing context."
        ),
        response_instruction=(
            "When legal language is quoted or paraphrased, stay close to the wording in the cited context and do not "
            "invent legal conclusions that the documents do not support."
        ),
    ),
    "medical": DomainPromptProfile(
        system_instruction=(
            "Treat the context as medical material. Preserve diagnoses, symptoms, medications, dosages, units, dates, "
            "vitals, assessments, and plans exactly, and separate documented facts from inference."
        ),
        response_instruction=(
            "If the chart, note, or results do not support a diagnosis, treatment step, or risk statement, say that "
            "explicitly instead of guessing."
        ),
    ),
    "cisco": DomainPromptProfile(
        system_instruction=(
            "Treat the context as Cisco networking material. Preserve CLI syntax, interface identifiers, VLAN values, "
            "ACL names, routing protocol settings, and indentation exactly as grounded in the retrieved context."
        ),
        response_instruction=(
            "Use fenced code blocks for configuration snippets when helpful, and never normalize or rewrite commands in "
            "a way that changes their syntax."
        ),
    ),
}


def prompt_profile_for(domain: str | None) -> DomainPromptProfile | None:
    if not domain:
        return None
    return PROMPT_PROFILES.get(domain)
