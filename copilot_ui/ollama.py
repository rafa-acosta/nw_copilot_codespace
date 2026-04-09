"""Ollama client helpers for fully local GUI inference."""

from __future__ import annotations

from collections.abc import Sequence
import os
from typing import Any

import requests


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
FIXED_OLLAMA_MODEL = "llama3.2:3b"
DEFAULT_OLLAMA_CHAT_MODEL = FIXED_OLLAMA_MODEL
DEFAULT_OLLAMA_EMBED_MODEL = FIXED_OLLAMA_MODEL
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120.0


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


class OllamaError(RuntimeError):
    """Raised when the local Ollama daemon or a model request fails."""


class OllamaClient:
    """Thin JSON client for the local Ollama HTTP API."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        chat_model: str = DEFAULT_OLLAMA_CHAT_MODEL,
        embedding_model: str = DEFAULT_OLLAMA_EMBED_MODEL,
        timeout_seconds: float = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Ollama base_url is required")
        if not chat_model.strip():
            raise ValueError("Ollama chat_model is required")
        if not embedding_model.strip():
            raise ValueError("Ollama embedding_model is required")
        if timeout_seconds <= 0:
            raise ValueError("Ollama timeout_seconds must be positive")

        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model.strip()
        self.embedding_model = embedding_model.strip()
        self.timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    @classmethod
    def from_env(cls) -> "OllamaClient":
        """Build an Ollama client from environment configuration."""

        return cls(
            base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
            chat_model=FIXED_OLLAMA_MODEL,
            embedding_model=FIXED_OLLAMA_MODEL,
            timeout_seconds=_positive_float_from_env(
                "OLLAMA_TIMEOUT_SECONDS",
                DEFAULT_OLLAMA_TIMEOUT_SECONDS,
            ),
        )

    def with_models(
        self,
        *,
        chat_model: str | None = None,
        embedding_model: str | None = None,
    ) -> "OllamaClient":
        """Clone the client while changing one or both active model names."""

        return type(self)(
            base_url=self.base_url,
            chat_model=chat_model or self.chat_model,
            embedding_model=embedding_model or self.embedding_model,
            timeout_seconds=self.timeout_seconds,
            session=self._session,
        )

    def list_models(self) -> tuple[str, ...]:
        """Return installed local Ollama model names."""

        response = self._request_json("/api/tags", method="GET")
        models = response.get("models")
        if not isinstance(models, list):
            raise OllamaError("Ollama returned an unexpected model list payload")

        names = sorted(
            {
                str(item.get("name", "")).strip()
                for item in models
                if isinstance(item, dict) and str(item.get("name", "")).strip()
            }
        )
        return tuple(names)

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """Embed documents with Ollama, falling back for older daemon versions."""

        if not texts:
            return []

        response = self._request_json(
            "/api/embed",
            payload={"model": self.embedding_model, "input": list(texts)},
            allow_404=True,
        )
        if response is None:
            return [self._legacy_embed_text(text) for text in texts]

        embeddings = response.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise OllamaError("Ollama returned an unexpected embeddings payload")
        return [self._coerce_embedding(vector) for vector in embeddings]

    def embed_query(self, text: str) -> tuple[float, ...]:
        """Embed a single query string."""

        embeddings = self.embed_documents([text])
        if not embeddings:
            raise OllamaError("Ollama did not return an embedding for the query")
        return embeddings[0]

    def chat(self, messages: Sequence[dict[str, str]], *, temperature: float = 0.1) -> str:
        """Run a non-streaming chat completion against Ollama."""

        response = self._request_json(
            "/api/chat",
            payload={
                "model": self.chat_model,
                "messages": list(messages),
                "stream": False,
                "options": {"temperature": temperature},
            },
        )

        message = response.get("message")
        if not isinstance(message, dict):
            raise OllamaError("Ollama returned an unexpected chat payload")

        content = str(message.get("content", "")).strip()
        if not content:
            raise OllamaError("Ollama returned an empty answer")
        return content

    def _legacy_embed_text(self, text: str) -> tuple[float, ...]:
        response = self._request_json(
            "/api/embeddings",
            payload={"model": self.embedding_model, "prompt": text},
        )
        return self._coerce_embedding(response.get("embedding"))

    def _request_json(
        self,
        path: str,
        *,
        method: str = "POST",
        payload: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any] | None:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(
                method,
                url,
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.RequestException as exc:
            raise OllamaError(
                "Could not reach Ollama. Start `ollama serve` and make sure the required "
                f"model `{FIXED_OLLAMA_MODEL}` is available at {self.base_url}."
            ) from exc

        if allow_404 and response.status_code == 404:
            return None

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise OllamaError(self._format_http_error(path, response)) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaError(f"Ollama returned invalid JSON from {path}") from exc

        if not isinstance(data, dict):
            raise OllamaError(f"Ollama returned an unexpected JSON payload from {path}")
        if data.get("error"):
            raise OllamaError(str(data["error"]))
        return data

    def _format_http_error(self, path: str, response: requests.Response) -> str:
        message = ""
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        if isinstance(payload, dict) and payload.get("error"):
            message = str(payload["error"]).strip()
        elif response.text.strip():
            message = response.text.strip()
        else:
            message = f"HTTP {response.status_code}"

        return f"Ollama request to {path} failed: {message}"

    @staticmethod
    def _coerce_embedding(values: Any) -> tuple[float, ...]:
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
            raise OllamaError("Ollama returned an invalid embedding vector")

        vector = tuple(float(value) for value in values)
        if not vector:
            raise OllamaError("Ollama returned an empty embedding vector")
        return vector
