"""Answer synthesis for the local GUI copilot."""

from __future__ import annotations

from abc import ABC, abstractmethod
import re
from typing import Sequence

from copilot_ui.models import ChatCitation, GeneratedAnswer
from copilot_ui.ollama import OllamaClient
from domain_routing import prompt_profile_for
from retrieval.models import RetrievalResponse, RetrievedChunk
from retrieval.utils import contains_term, normalize_user_query, tokenize_preserving_technical


class AnswerGenerator(ABC):
    """Transforms retrieval results into a user-facing assistant answer."""

    @abstractmethod
    def generate(self, query: str, retrieval_response: RetrievalResponse) -> GeneratedAnswer:
        raise NotImplementedError

    @staticmethod
    def _domain_meta(retrieval_response: RetrievalResponse) -> dict[str, object]:
        return {
            "domain": retrieval_response.domain,
            "domain_mode": retrieval_response.domain_mode,
            "domain_confidence": retrieval_response.domain_confidence,
            "domain_reason": retrieval_response.domain_reason,
            "domain_filter_applied": retrieval_response.domain_filter_applied,
        }


class GroundedAnswerGenerator(AnswerGenerator):
    """Local extractive answer synthesizer with source citations."""

    def generate(self, query: str, retrieval_response: RetrievalResponse) -> GeneratedAnswer:
        if not retrieval_response.results:
            scoped_label = (
                f" in the selected {retrieval_response.domain} documents"
                if retrieval_response.domain and retrieval_response.domain_filter_applied
                else " in the indexed documents yet"
            )
            return GeneratedAnswer(
                content=(
                    f"I could not find a grounded answer{scoped_label}.\n\n"
                    "Try broadening the query, switching retrieval mode, or loading more relevant files."
                ),
                meta={
                    "retrieval_mode": retrieval_response.retrieval_mode,
                    "latency_ms": retrieval_response.timings.total_ms,
                    "result_count": 0,
                    **self._domain_meta(retrieval_response),
                },
            )

        citations = tuple(self._to_citation(query, result) for result in retrieval_response.results[:4])
        if retrieval_response.domain:
            route_descriptor = (
                f"{retrieval_response.domain} corpus"
                if retrieval_response.domain_filter_applied
                else f"{retrieval_response.domain}-leaning corpus"
            )
            intro = f"Here are the strongest grounded matches I found in the routed {route_descriptor}:"
        else:
            intro = "Here are the strongest grounded matches I found in the indexed documents:"
        answer_lines = [
            intro,
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
                **self._domain_meta(retrieval_response),
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


class OllamaAnswerGenerator(GroundedAnswerGenerator):
    """Ollama-backed grounded answer synthesis."""

    def __init__(self, client: OllamaClient | None = None, *, max_context_chunks: int = 4) -> None:
        if max_context_chunks <= 0:
            raise ValueError("max_context_chunks must be positive")
        self.client = client or OllamaClient.from_env()
        self.max_context_chunks = max_context_chunks

    def generate(self, query: str, retrieval_response: RetrievalResponse) -> GeneratedAnswer:
        if not retrieval_response.results:
            return super().generate(query, retrieval_response)

        selected_results = retrieval_response.results[: self.max_context_chunks]
        citations = tuple(self._to_citation(query, result) for result in selected_results)
        prompt_profile = prompt_profile_for(retrieval_response.domain)
        system_prompt = (
            "You are a retrieval-augmented assistant. Answer only from the provided document context. "
            "If the answer is not supported by the context, say so clearly. Keep the response concise and "
            "technical, and cite source labels in square brackets. Do not expose hidden reasoning, thinking "
            "traces, or chain-of-thought."
        )
        if prompt_profile is not None:
            system_prompt = f"{system_prompt} {prompt_profile.system_instruction}"
        content = self.client.chat(
            (
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": self._build_prompt(query, selected_results, citations, retrieval_response),
                },
            )
        )
        content = self._sanitize_answer_content(content)

        return GeneratedAnswer(
            content=content,
            citations=citations,
            meta={
                "retrieval_mode": retrieval_response.retrieval_mode,
                "latency_ms": retrieval_response.timings.total_ms,
                "result_count": retrieval_response.top_k_results,
                "answer_provider": "ollama",
                "answer_model": self.client.chat_model,
                **self._domain_meta(retrieval_response),
            },
        )

    def _build_prompt(
        self,
        query: str,
        results: Sequence[RetrievedChunk],
        citations: Sequence[ChatCitation],
        retrieval_response: RetrievalResponse,
    ) -> str:
        prompt_parts = [
            f"Question: {query}",
            "",
        ]

        if retrieval_response.domain:
            prompt_parts.extend(
                [
                    f"Routed domain: {retrieval_response.domain}",
                    f"Routing mode: {retrieval_response.domain_mode or 'automatic'}",
                    f"Domain confidence: {(retrieval_response.domain_confidence or 0.0):.2f}",
                    f"Domain filter applied: {'yes' if retrieval_response.domain_filter_applied else 'no'}",
                    f"Routing reason: {retrieval_response.domain_reason or 'n/a'}",
                    "",
                ]
            )

        prompt_parts.append("Retrieved context:")

        for index, (result, citation) in enumerate(zip(results, citations), start=1):
            prompt_parts.extend(
                [
                    f"Source {index}",
                    f"Label: {citation.label}",
                    f"Source type: {citation.source_type}",
                    f"Domain: {result.metadata.get('domain') or result.metadata.get('custom', {}).get('domain') or 'n/a'}",
                    f"Relevance score: {citation.score:.3f}",
                    "Chunk text:",
                    result.text.strip(),
                    "",
                ]
            )

        prompt_parts.append("Write a grounded answer using only the context above.")
        prompt_parts.append("If the context is incomplete or conflicting, say that explicitly.")

        prompt_profile = prompt_profile_for(retrieval_response.domain)
        if prompt_profile is not None:
            prompt_parts.append(prompt_profile.response_instruction)

        return "\n".join(prompt_parts).strip()

    @staticmethod
    def _sanitize_answer_content(content: str) -> str:
        cleaned = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
        return cleaned or content.strip()
