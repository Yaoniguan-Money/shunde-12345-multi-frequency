"""Local-only adapters. Public URLs remain rejected at this seam."""

import hashlib
import json
from collections.abc import Iterable
from typing import Any, cast

import httpx

from backend.app.domain.types import EmbeddingRequest, EmbeddingResult, VersionTrace
from backend.app.infrastructure.ai.openai_compatible import (
    OpenAICompatibleChatAdapter,
    OpenAICompatibleEmbeddingAdapter,
    OpenAICompatibleUnavailable,
    ensure_http_url,
)


class LocalModelUnavailable(RuntimeError):
    """A configured local model endpoint cannot serve a real request."""


class OpenAICompatibleLLMProvider(OpenAICompatibleChatAdapter):
    """Backward-compatible local OpenAI-compatible chat adapter."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        *,
        timeout_seconds: float = 120.0,
        concurrency: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url,
            model_id,
            provider="local-openai-compatible",
            allow_public_url=False,
            timeout_seconds=timeout_seconds,
            concurrency=concurrency,
            transport=transport,
        )


class LocalOpenAICompatibleEmbeddingProvider(OpenAICompatibleEmbeddingAdapter):
    """Local OpenAI-compatible embedding endpoint with the same URL guard."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        *,
        timeout_seconds: float = 120.0,
        concurrency: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url,
            model_id,
            provider="local-openai-compatible",
            allow_public_url=False,
            timeout_seconds=timeout_seconds,
            concurrency=concurrency,
            transport=transport,
        )


class OllamaEmbeddingProvider:
    """Use Ollama's local `/api/embed` endpoint for batched embeddings."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        *,
        timeout_seconds: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = ensure_http_url(base_url, allow_public=False)
        self._model_id = model_id
        self._timeout = timeout_seconds
        self._transport = transport
        self._config_hash = _configuration_hash(
            ("local-ollama", self._base_url, self._model_id, self._timeout)
        )

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                raw_payload = response.json()
                if not isinstance(raw_payload, dict):
                    raise LocalModelUnavailable("local embedding /api/tags response is malformed")
                payload = cast(dict[str, Any], raw_payload)
            raw_models = payload.get("models", [])
            if not isinstance(raw_models, list):
                raise LocalModelUnavailable("local embedding /api/tags response is malformed")
            models = cast(list[object], raw_models)
            names = {
                str(cast(dict[str, Any], item).get("name"))
                for item in models
                if isinstance(item, dict) and cast(dict[str, Any], item).get("name")
            }
            normalized_names = {name.split(":", 1)[0] for name in names}
            configured_name = self._model_id.split(":", 1)[0]
            if not names or (
                self._model_id not in names and configured_name not in normalized_names
            ):
                raise LocalModelUnavailable(f"embedding model {self._model_id!r} is not pulled")
            return self._model_id
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise LocalModelUnavailable("local embedding health check failed") from error

    async def embed_batch(
        self, requests: tuple[EmbeddingRequest, ...]
    ) -> tuple[EmbeddingResult, ...]:
        if not requests:
            return ()
        payload = {"model": self._model_id, "input": [request.text for request in requests]}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(f"{self._base_url}/api/embed", json=payload)
                response.raise_for_status()
                raw_body = response.json()
                if not isinstance(raw_body, dict):
                    raise LocalModelUnavailable("embedding response is malformed")
                body = cast(dict[str, Any], raw_body)
            raw_vectors = body.get("embeddings")
            if not isinstance(raw_vectors, list):
                raise LocalModelUnavailable("embedding response count does not match request count")
            vectors = cast(list[object], raw_vectors)
            if len(vectors) != len(requests):
                raise LocalModelUnavailable("embedding response count does not match request count")
            results: list[EmbeddingResult] = []
            for request, vector in zip(requests, vectors, strict=True):
                vector_values = cast(list[object], vector) if isinstance(vector, list) else []
                if not vector_values or not all(
                    isinstance(value, (int, float)) for value in vector_values
                ):
                    raise LocalModelUnavailable(
                        f"embedding vector is malformed for {request.item_id}"
                    )
                results.append(
                    EmbeddingResult(
                        request.item_id,
                        tuple(float(cast(int | float, value)) for value in vector_values),
                        self._model_id,
                        VersionTrace(
                            model_id=self._model_id,
                            model_config_hash=self._config_hash,
                            schema_version=request.schema_version,
                            knowledge_snapshot_id=None,
                            pipeline_version=request.pipeline_version,
                            provider="local-ollama",
                        ),
                    )
                )
            return tuple(results)
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise LocalModelUnavailable("embedding generation failed") from error


def _configuration_hash(values: Iterable[object]) -> str:
    payload = json.dumps(list(values), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "LocalModelUnavailable",
    "LocalOpenAICompatibleEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "OpenAICompatibleLLMProvider",
    "OpenAICompatibleUnavailable",
]
