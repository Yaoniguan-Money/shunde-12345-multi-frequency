import asyncio
import hashlib
import ipaddress
import json
from collections.abc import Iterable
from typing import Any, cast
from urllib.parse import urlparse

import httpx

from backend.app.domain.types import (
    EmbeddingRequest,
    EmbeddingResult,
    LLMRequest,
    LLMResult,
    VersionTrace,
)


class LocalModelUnavailable(RuntimeError):
    """A configured local model endpoint cannot serve a real request."""


def _ensure_local_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("local model base URL must be an HTTP(S) URL")
    hostname = parsed.hostname.casefold()
    is_local = hostname in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
    if not is_local:
        try:
            is_local = ipaddress.ip_address(hostname).is_private
        except ValueError:
            is_local = False
    if not is_local:
        raise ValueError("cloud model endpoints are not allowed; configure a local URL")
    return base_url.rstrip("/")


def _configuration_hash(values: Iterable[object]) -> str:
    payload = json.dumps(list(values), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class OpenAICompatibleLLMProvider:
    """Call a local OpenAI-compatible chat endpoint and require structured JSON."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        *,
        timeout_seconds: float = 120.0,
        concurrency: int = 1,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be positive")
        self._base_url = _ensure_local_url(base_url)
        self._model_id = model_id
        self._timeout = timeout_seconds
        self._concurrency = concurrency
        self._config_hash = _configuration_hash(
            (self._base_url, self._model_id, self._timeout, self._concurrency)
        )

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/v1/models")
                response.raise_for_status()
                raw_payload = response.json()
                if not isinstance(raw_payload, dict):
                    raise LocalModelUnavailable("local model /v1/models response is malformed")
                payload = cast(dict[str, Any], raw_payload)
            raw_models = payload.get("data", [])
            if not isinstance(raw_models, list):
                raise LocalModelUnavailable("local model /v1/models response is malformed")
            models = cast(list[object], raw_models)
            available = {
                str(cast(dict[str, Any], item).get("id"))
                for item in models
                if isinstance(item, dict) and cast(dict[str, Any], item).get("id")
            }
            if not available or self._model_id not in available:
                raise LocalModelUnavailable(f"model {self._model_id!r} is not loaded")
            return self._model_id
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise LocalModelUnavailable("local LLM health check failed") from error

    async def generate_batch(self, requests: tuple[LLMRequest, ...]) -> tuple[LLMResult, ...]:
        if not requests:
            return ()
        semaphore = asyncio.Semaphore(self._concurrency)
        async with httpx.AsyncClient(timeout=self._timeout) as client:

            async def generate(request: LLMRequest) -> LLMResult:
                async with semaphore:
                    return await self._generate_one(client, request)

            return tuple(await asyncio.gather(*(generate(request) for request in requests)))

    async def _generate_one(self, client: httpx.AsyncClient, request: LLMRequest) -> LLMResult:
        schema_json = json.dumps(request.output_schema, ensure_ascii=False)
        payload = {
            "model": self._model_id,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是政务12345工单结构化抽取器。只能依据输入文本；未知字段使用 null、"
                        "空数组或 unresolved，不得编造地点、机构、事件或诉求。只返回 JSON。\n"
                        f"输出 JSON Schema：{schema_json}"
                    ),
                },
                {"role": "user", "content": request.prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            response = await client.post(f"{self._base_url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            body = cast(dict[str, Any], response.json())
            raw_choices = body.get("choices")
            if not isinstance(raw_choices, list) or not raw_choices:
                raise LocalModelUnavailable("local LLM response has no choices")
            choices = cast(list[object], raw_choices)
            first_choice = choices[0]
            choice_data = (
                cast(dict[str, Any], first_choice) if isinstance(first_choice, dict) else None
            )
            message = choice_data.get("message") if choice_data is not None else None
            message_data = cast(dict[str, Any], message) if isinstance(message, dict) else None
            content = message_data.get("content") if message_data is not None else None
            structured = self._parse_json_content(content)
        except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise LocalModelUnavailable(
                f"structured inference failed for {request.request_id}"
            ) from error
        trace = VersionTrace(
            model_id=self._model_id,
            model_config_hash=self._config_hash,
            schema_version=request.schema_version,
            knowledge_snapshot_id=None,
            pipeline_version=request.pipeline_version,
        )
        return LLMResult(request.request_id, structured, trace)

    @staticmethod
    def _parse_json_content(content: object) -> dict[str, object]:
        if isinstance(content, dict):
            return cast(dict[str, object], content)
        if not isinstance(content, str):
            raise LocalModelUnavailable("local LLM content is not JSON text")
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```").removeprefix("json").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise LocalModelUnavailable("local LLM JSON root must be an object")
        return cast(dict[str, object], parsed)


class OllamaEmbeddingProvider:
    """Use Ollama's local `/api/embed` endpoint for batched embeddings."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        *,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base_url = _ensure_local_url(base_url)
        self._model_id = model_id
        self._timeout = timeout_seconds

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
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
            async with httpx.AsyncClient(timeout=self._timeout) as client:
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
                    )
                )
            return tuple(results)
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise LocalModelUnavailable("embedding generation failed") from error
