"""Answer synthesis for the local GUI copilot."""

from __future__ import annotations

from abc import ABC, abstractmethod
import re

from copilot_ui.models import ChatCitation, GeneratedAnswer
from retrieval.models import RetrievalResponse, RetrievedChunk
from retrieval.utils import contains_term, normalize_user_query, tokenize_preserving_technical


class AnswerGenerator(ABC):
    """Transforms retrieval results into a user-facing assistant answer."""

    @abstractmethod
    def generate(self, query: str, retrieval_response: RetrievalResponse) -> GeneratedAnswer:
        raise NotImplementedError


class GroundedAnswerGenerator(AnswerGenerator):
    """Local extractive answer synthesizer with source citations."""

    def generate(self, query: str, retrieval_response: RetrievalResponse) -> GeneratedAnswer:
        if not retrieval_response.results:
            return GeneratedAnswer(
                content=(
                    "I could not find a grounded answer in the indexed documents yet.\n\n"
                    "Try broadening the query, switching retrieval mode, or loading more relevant files."
                ),
                meta={
                    "retrieval_mode": retrieval_response.retrieval_mode,
                    "latency_ms": retrieval_response.timings.total_ms,
                    "result_count": 0,
                },
            )

        citations = tuple(self._to_citation(query, result) for result in retrieval_response.results[:4])
        answer_lines = [
            "Here are the strongest grounded matches I found in the indexed documents:",
            "",
        ]
        for citation in citations:
            answer_lines.append(f"- {citation.excerpt} [{citation.label}]")

        return GeneratedAnswer(
            content="\n".join(answer_lines).strip(),
            citations=citations,
            meta={
                "retrieval_mode": retrieval_response.retrieval_mode,
                "latency_ms": retrieval_response.timings.total_ms,
                "result_count": retrieval_response.top_k_results,
            },
        )

    def _to_citation(self, query: str, result: RetrievedChunk) -> ChatCitation:
        return ChatCitation(
            chunk_id=result.chunk_id,
            label=self._format_label(result),
            source_type=result.source_type,
            score=result.score,
            excerpt=self._best_excerpt(result.text, query),
            metadata=result.metadata,
        )

    @staticmethod
    def _format_label(result: RetrievedChunk) -> str:
        metadata = result.metadata
        filename = metadata.get("filename") or "unknown"
        if metadata.get("page_number") is not None:
            return f"{filename} • p.{metadata['page_number']}"
        if metadata.get("section"):
            return f"{filename} • {metadata['section']}"
        if metadata.get("sheet_name"):
            row_start = metadata.get("row_start")
            row_end = metadata.get("row_end")
            if row_start and row_end:
                return f"{filename} • {metadata['sheet_name']} • rows {row_start}-{row_end}"
            return f"{filename} • {metadata['sheet_name']}"
        if metadata.get("json_key_path"):
            return f"{filename} • {metadata['json_key_path']}"
        if metadata.get("cisco_section"):
            return f"{filename} • {metadata.get('cisco_feature') or 'cisco'} {metadata['cisco_section']}"
        return f"{filename} • chunk {result.chunk_id[:8]}"

    @staticmethod
    def _best_excerpt(text: str, query: str) -> str:
        normalized_query = normalize_user_query(query)
        terms = tokenize_preserving_technical(normalized_query, minimum_length=2)
        candidates = [part.strip() for part in re.split(r"\n+|(?<=[.!?])\s+", text) if part.strip()]
        if not candidates:
            return text[:220].strip()

        scored: list[tuple[int, str]] = []
        for candidate in candidates:
            score = 0
            for term in terms:
                if contains_term(candidate, term):
                    score += 2
            if contains_term(candidate, normalized_query):
                score += 3
            scored.append((score, candidate))

        scored.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
        best = scored[0][1]
        return best[:240].strip()
