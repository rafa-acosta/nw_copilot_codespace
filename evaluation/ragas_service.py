"""Lazy RAGAS adapter used only when the user requests an evaluation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
import re
import threading
from typing import Any, Iterable

from evaluation.models import RagasEvaluationPayload, RagasEvaluationResult, RagasMetricResult


DEFAULT_BASE_METRICS = (
    "faithfulness",
    "context_utilization",
)
REFERENCE_METRICS = (
    "context_precision",
    "context_recall",
)


class RagasEvaluationError(RuntimeError):
    """Raised when demand-driven RAGAS evaluation cannot be started."""


@dataclass(slots=True)
class RagasEvaluatorConfig:
    """Runtime configuration for RAGAS judge models."""

    provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str | None = "text-embedding-3-small"
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 45.0
    system_prompt: str = "You are a careful evaluator for retrieval-augmented generation answers."
    reasoning_effort: str | None = None
    max_tokens: int | None = None

    @classmethod
    def from_ollama(
        cls,
        *,
        base_url: str,
        chat_model: str,
        embedding_model: str | None,
    ) -> "RagasEvaluatorConfig":
        return cls(
            provider="openai",
            llm_model=chat_model,
            embedding_model=embedding_model,
            api_key="ollama",
            base_url=_openai_compatible_base_url(base_url),
            timeout_seconds=_positive_float_from_env("RAGAS_TIMEOUT_SECONDS", 45.0),
            reasoning_effort=_ragas_reasoning_effort(chat_model),
            max_tokens=_ragas_max_tokens(chat_model),
        )

    @classmethod
    def from_env(cls) -> "RagasEvaluatorConfig":
        base_url = os.getenv("RAGAS_OPENAI_BASE_URL")
        if not base_url and os.getenv("OLLAMA_BASE_URL"):
            base_url = _openai_compatible_base_url(os.environ["OLLAMA_BASE_URL"])

        llm_model = os.getenv("RAGAS_LLM_MODEL") or os.getenv("OLLAMA_CHAT_MODEL") or "gpt-4o-mini"
        api_key = (
            os.getenv("RAGAS_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ("ollama" if base_url else None)
        )
        return cls(
            provider=os.getenv("RAGAS_PROVIDER", "openai"),
            llm_model=llm_model,
            embedding_model=os.getenv("RAGAS_EMBED_MODEL") or os.getenv("OLLAMA_EMBED_MODEL") or "text-embedding-3-small",
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=_positive_float_from_env("RAGAS_TIMEOUT_SECONDS", 45.0),
            reasoning_effort=_ragas_reasoning_effort(llm_model),
            max_tokens=_ragas_max_tokens(llm_model),
        )

    @staticmethod
    def has_env_override() -> bool:
        return any(
            os.getenv(name)
            for name in (
                "RAGAS_PROVIDER",
                "RAGAS_LLM_MODEL",
                "RAGAS_EMBED_MODEL",
                "RAGAS_OPENAI_BASE_URL",
                "RAGAS_API_KEY",
                "OPENAI_API_KEY",
                "RAGAS_REASONING_EFFORT",
                "RAGAS_MAX_TOKENS",
                "RAGAS_MAX_COMPLETION_TOKENS",
            )
        )


class RagasEvaluator:
    """Small facade around RAGAS collection metrics.

    Imports and model clients are created lazily so the normal chat path never pays
    RAGAS import time, network calls, or judge-model latency.
    """

    def __init__(self, config: RagasEvaluatorConfig | None = None) -> None:
        self.config = config or RagasEvaluatorConfig.from_env()
        self._client: Any | None = None
        self._llm: Any | None = None
        self._embeddings: Any | None = None

    def evaluate(
        self,
        payload: RagasEvaluationPayload,
        *,
        metrics: Iterable[str] | None = None,
    ) -> RagasEvaluationResult:
        if not payload.retrieved_contexts:
            raise RagasEvaluationError("This answer has no retrieved contexts to evaluate.")
        if not payload.response.strip():
            raise RagasEvaluationError("This answer is empty and cannot be evaluated.")

        metric_names = self._resolve_metric_names(metrics, reference=payload.reference)
        metric_results = tuple(self._score_metric(metric_name, payload) for metric_name in metric_names)
        return RagasEvaluationResult(
            metrics=metric_results,
            provider=self.config.provider,
            model=self.config.llm_model,
            embedding_model=self.config.embedding_model,
            reference_provided=bool(payload.reference),
            retrieved_context_count=len(payload.retrieved_contexts),
        )

    def _resolve_metric_names(self, metrics: Iterable[str] | None, *, reference: str | None) -> tuple[str, ...]:
        if metrics:
            return tuple(dict.fromkeys(_normalize_metric_name(metric) for metric in metrics if metric))

        configured_metrics = os.getenv("RAGAS_METRICS")
        if configured_metrics:
            return tuple(
                dict.fromkeys(
                    _normalize_metric_name(metric)
                    for metric in configured_metrics.split(",")
                    if metric.strip()
                )
            )

        names = DEFAULT_BASE_METRICS
        if reference:
            names = (*names, *REFERENCE_METRICS)
        return names

    def _score_metric(self, metric_name: str, payload: RagasEvaluationPayload) -> RagasMetricResult:
        try:
            return _run_async(
                asyncio.wait_for(
                    self._score_metric_async(metric_name, payload),
                    timeout=self.config.timeout_seconds,
                )
            )
        except RagasEvaluationError:
            raise
        except TimeoutError:
            return RagasMetricResult(
                name=metric_name,
                score=None,
                error=f"RAGAS metric timed out after {self.config.timeout_seconds:.0f}s.",
            )
        except Exception as exc:  # noqa: BLE001
            return RagasMetricResult(name=metric_name, score=None, error=str(exc))

    async def _score_metric_async(self, metric_name: str, payload: RagasEvaluationPayload) -> RagasMetricResult:
        scorer, kwargs = self._build_metric(metric_name, payload)
        result = await scorer.ascore(**kwargs)
        if isinstance(result, RagasMetricResult):
            return RagasMetricResult(
                name=metric_name,
                score=result.score,
                reason=result.reason,
                error=result.error,
                skipped=result.skipped,
            )
        score = getattr(result, "value", result)
        reason = getattr(result, "reason", None)
        return RagasMetricResult(name=metric_name, score=float(score), reason=reason)

    def _build_metric(self, metric_name: str, payload: RagasEvaluationPayload) -> tuple[Any, dict[str, Any]]:
        if metric_name in REFERENCE_METRICS and not payload.reference:
            return _SkippedMetric(), {"reason": f"{metric_name} requires a reference answer."}
        if metric_name == "answer_relevancy" and self.config.embedding_model is None:
            return _SkippedMetric(), {"reason": "No embedding model is configured for answer_relevancy."}

        self._ensure_clients()

        try:
            from ragas.metrics.collections import (  # type: ignore[import-not-found]
                AnswerRelevancy,
                ContextPrecision,
                ContextRecall,
                ContextUtilization,
                Faithfulness,
            )
        except ImportError as exc:
            raise RagasEvaluationError(
                "RAGAS is not installed. Install project requirements first: `pip install -r requirements.txt`."
            ) from exc

        if metric_name == "faithfulness":
            return (
                Faithfulness(llm=self._llm),
                {
                    "user_input": payload.user_input,
                    "response": payload.response,
                    "retrieved_contexts": list(payload.retrieved_contexts),
                },
            )

        if metric_name == "answer_relevancy":
            self._ensure_embeddings()
            return (
                AnswerRelevancy(llm=self._llm, embeddings=self._embeddings),
                {
                    "user_input": payload.user_input,
                    "response": payload.response,
                },
            )

        if metric_name == "context_utilization":
            return (
                ContextUtilization(llm=self._llm),
                {
                    "user_input": payload.user_input,
                    "response": payload.response,
                    "retrieved_contexts": list(payload.retrieved_contexts),
                },
            )

        if metric_name == "context_precision":
            return (
                ContextPrecision(llm=self._llm),
                {
                    "user_input": payload.user_input,
                    "reference": payload.reference,
                    "retrieved_contexts": list(payload.retrieved_contexts),
                },
            )

        if metric_name == "context_recall":
            return (
                ContextRecall(llm=self._llm),
                {
                    "user_input": payload.user_input,
                    "reference": payload.reference,
                    "retrieved_contexts": list(payload.retrieved_contexts),
                },
            )

        raise RagasEvaluationError(f"Unsupported RAGAS metric: {metric_name}")

    def _ensure_clients(self) -> None:
        if self._llm is not None:
            return

        try:
            from openai import AsyncOpenAI
            from ragas.llms import llm_factory  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RagasEvaluationError(
                "RAGAS evaluation requires `ragas` and `openai`. Install project requirements first."
            ) from exc

        if not self.config.api_key:
            raise RagasEvaluationError(
                "RAGAS evaluation needs a judge model API key. Set RAGAS_API_KEY/OPENAI_API_KEY, "
                "or run with Ollama so the local OpenAI-compatible endpoint can be used."
            )

        client_kwargs: dict[str, Any] = {
            "api_key": self.config.api_key,
            "timeout": self.config.timeout_seconds,
        }
        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url
        self._client = AsyncOpenAI(**client_kwargs)

        self._llm = llm_factory(
            self.config.llm_model,
            provider=self.config.provider,
            client=self._client,
            system_prompt=self.config.system_prompt,
        )
        self._apply_reasoning_model_overrides()

    def _ensure_embeddings(self) -> None:
        if self._embeddings is not None:
            return
        if self.config.embedding_model:
            if self._client is None:
                self._ensure_clients()
            try:
                from ragas.embeddings.base import embedding_factory  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RagasEvaluationError(
                    "RAGAS answer_relevancy requires `ragas` embedding support. Install project requirements first."
                ) from exc

            self._embeddings = embedding_factory(
                self.config.provider,
                model=self.config.embedding_model,
                client=self._client,
            )

    def _apply_reasoning_model_overrides(self) -> None:
        if self.config.provider.casefold() != "openai":
            return
        if not _is_reasoning_model_name(self.config.llm_model):
            return
        model_args = getattr(self._llm, "model_args", None)
        if not isinstance(model_args, dict):
            return

        # GPT-5/o-series models can burn the whole output budget on reasoning before
        # returning the structured JSON RAGAS expects. We force Chat Completions-safe
        # parameters here so newer dotted model IDs like gpt-5.5 also behave.
        model_args["temperature"] = 1.0
        model_args.pop("top_p", None)

        if self.config.reasoning_effort:
            model_args["reasoning_effort"] = self.config.reasoning_effort

        max_tokens = self.config.max_tokens
        if max_tokens is not None:
            model_args.pop("max_tokens", None)
            model_args["max_completion_tokens"] = max_tokens


class _SkippedMetric:
    async def ascore(self, *, reason: str) -> RagasMetricResult:
        return RagasMetricResult(name="skipped", score=None, reason=reason, skipped=True)


def _normalize_metric_name(metric_name: str) -> str:
    normalized = metric_name.strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "response_relevancy": "answer_relevancy",
        "answer_relevance": "answer_relevancy",
        "context_precision_without_reference": "context_utilization",
        "context_utilisation": "context_utilization",
    }
    return aliases.get(normalized, normalized)


def _positive_float_from_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


def _optional_positive_int_from_env(*names: str) -> int | None:
    for name in names:
        raw_value = os.getenv(name)
        if raw_value is None or not raw_value.strip():
            continue
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise ValueError(f"{name} must be a positive integer") from exc
        if value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value
    return None


def _ragas_reasoning_effort(model_name: str) -> str | None:
    configured = os.getenv("RAGAS_REASONING_EFFORT")
    if configured is not None and configured.strip():
        return configured.strip()
    if _is_reasoning_model_name(model_name):
        return "low"
    return None


def _ragas_max_tokens(model_name: str) -> int | None:
    configured = _optional_positive_int_from_env(
        "RAGAS_MAX_TOKENS",
        "RAGAS_MAX_COMPLETION_TOKENS",
    )
    if configured is not None:
        return configured
    if _is_reasoning_model_name(model_name):
        return 4096
    return None


def _is_reasoning_model_name(model_name: str) -> bool:
    normalized = model_name.strip().casefold()
    if not normalized:
        return False
    if re.match(r"^o[1-9](?:$|[-_])", normalized):
        return True
    if normalized == "codex-mini":
        return True

    match = re.match(r"^gpt-(\d+)(?:\.\d+)?(?:$|[-_])", normalized)
    if match is None:
        return False
    return int(match.group(1)) >= 5


def _openai_compatible_base_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    return trimmed if trimmed.endswith("/v1") else f"{trimmed}/v1"


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list[Any] = []
    error: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:  # noqa: BLE001
            error.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]
