"""Shared OpenAI-compatible HTTP implementations behind local/remote adapters."""

import asyncio
import hashlib
import ipaddress
import json
from collections.abc import Iterable
from typing import Any, cast
from urllib.parse import urlparse

import httpx
from pydantic import SecretStr

from backend.app.domain.types import (
    EmbeddingRequest,
    EmbeddingResult,
    LLMRequest,
    LLMResult,
    VersionTrace,
)

_DEFAULT_MAX_OUTPUT_TOKENS = 1024


class OpenAICompatibleUnavailable(RuntimeError):
    """A configured OpenAI-compatible endpoint cannot serve a real request."""


def ensure_http_url(base_url: str, *, allow_public: bool) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("model base URL must be an HTTP(S) URL")
    if not allow_public:
        hostname = parsed.hostname.casefold()
        is_local = hostname in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
        if not is_local:
            try:
                is_local = ipaddress.ip_address(hostname).is_private
            except ValueError:
                is_local = False
        if not is_local:
            raise ValueError("cloud model endpoints are not allowed in local mode")
    return base_url.rstrip("/")


def _configuration_hash(values: Iterable[object]) -> str:
    payload = json.dumps(list(values), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _headers(api_key: SecretStr | None) -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key.get_secret_value()}"
    return headers


class OpenAICompatibleChatAdapter:
    """Deep chat adapter; URL policy and provider label are supplied by its wrapper."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        *,
        provider: str,
        allow_public_url: bool,
        api_key: SecretStr | None = None,
        timeout_seconds: float = 120.0,
        concurrency: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be positive")
        self._base_url = ensure_http_url(base_url, allow_public=allow_public_url)
        self._api_base_url = self._base_url.removesuffix("/v1")
        self._model_id = model_id
        self._provider = provider
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._concurrency = concurrency
        self._transport = transport
        self._config_hash = _configuration_hash(
            (
                self._provider,
                self._api_base_url,
                self._model_id,
                self._timeout,
                self._concurrency,
                _DEFAULT_MAX_OUTPUT_TOKENS,
                "api-key-configured" if api_key is not None else "no-api-key",
            )
        )

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers=_headers(self._api_key),
                transport=self._transport,
            ) as client:
                response = await client.get(f"{self._api_base_url}/v1/models")
                response.raise_for_status()
                payload = _object(response.json(), "model health response")
            model_ids = _model_ids(payload)
            if not model_ids or self._model_id not in model_ids:
                raise OpenAICompatibleUnavailable(
                    f"model {self._model_id!r} is not available from configured endpoint"
                )
            return self._model_id
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise OpenAICompatibleUnavailable(
                "OpenAI-compatible model health check failed"
            ) from error

    async def generate_batch(self, requests: tuple[LLMRequest, ...]) -> tuple[LLMResult, ...]:
        if not requests:
            return ()
        semaphore = asyncio.Semaphore(self._concurrency)
        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers=_headers(self._api_key),
            transport=self._transport,
        ) as client:

            async def generate(request: LLMRequest) -> LLMResult:
                async with semaphore:
                    return await self._generate_one(client, request)

            return tuple(await asyncio.gather(*(generate(request) for request in requests)))

    async def _generate_one(self, client: httpx.AsyncClient, request: LLMRequest) -> LLMResult:
        schema_json = json.dumps(request.output_schema, ensure_ascii=False)
        payload = {
            "model": self._model_id,
            "temperature": 0,
            "max_tokens": _DEFAULT_MAX_OUTPUT_TOKENS,
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
            response = await client.post(f"{self._api_base_url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            body = _object(response.json(), "chat response")
            raw_choices = body.get("choices")
            if not isinstance(raw_choices, list) or not raw_choices:
                raise OpenAICompatibleUnavailable("chat response has no choices")
            choices = cast(list[object], raw_choices)
            first_choice: object = choices[0]
            choice_data = _object(first_choice, "chat choice")
            message_data = _object(choice_data.get("message"), "chat message")
            structured = _parse_json_content(message_data.get("content"), request.output_schema)
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise OpenAICompatibleUnavailable(
                f"structured inference failed for {request.request_id}"
            ) from error
        trace = VersionTrace(
            model_id=self._model_id,
            model_config_hash=self._config_hash,
            schema_version=request.schema_version,
            knowledge_snapshot_id=None,
            pipeline_version=request.pipeline_version,
            provider=self._provider,
        )
        return LLMResult(request.request_id, structured, trace)


class OpenAICompatibleEmbeddingAdapter:
    """Deep batch embedding adapter for OpenAI-compatible `/v1/embeddings`."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        *,
        provider: str,
        allow_public_url: bool,
        api_key: SecretStr | None = None,
        timeout_seconds: float = 120.0,
        concurrency: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be positive")
        self._base_url = ensure_http_url(base_url, allow_public=allow_public_url)
        self._api_base_url = self._base_url.removesuffix("/v1")
        self._model_id = model_id
        self._provider = provider
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._concurrency = concurrency
        self._transport = transport
        self._config_hash = _configuration_hash(
            (
                self._provider,
                self._api_base_url,
                self._model_id,
                self._timeout,
                self._concurrency,
                "api-key-configured" if api_key is not None else "no-api-key",
            )
        )

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers=_headers(self._api_key),
                transport=self._transport,
            ) as client:
                response = await client.get(f"{self._api_base_url}/v1/models")
                response.raise_for_status()
                payload = _object(response.json(), "embedding health response")
            model_ids = _model_ids(payload)
            if not model_ids or self._model_id not in model_ids:
                raise OpenAICompatibleUnavailable(
                    f"embedding model {self._model_id!r} is not available from configured endpoint"
                )
            return self._model_id
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise OpenAICompatibleUnavailable(
                "OpenAI-compatible embedding health check failed"
            ) from error

    async def embed_batch(
        self, requests: tuple[EmbeddingRequest, ...]
    ) -> tuple[EmbeddingResult, ...]:
        if not requests:
            return ()
        payload = {"model": self._model_id, "input": [request.text for request in requests]}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers=_headers(self._api_key),
                transport=self._transport,
            ) as client:
                response = await client.post(f"{self._api_base_url}/v1/embeddings", json=payload)
                response.raise_for_status()
                body = _object(response.json(), "embedding response")
            raw_data = body.get("data")
            if not isinstance(raw_data, list):
                raise OpenAICompatibleUnavailable("embedding response data is malformed")
            data_items = cast(list[object], raw_data)
            if len(data_items) != len(requests):
                raise OpenAICompatibleUnavailable(
                    "embedding response count does not match request count"
                )
            by_index: dict[int, list[float]] = {}
            for item in data_items:
                item_data = _object(item, "embedding item")
                index = item_data.get("index")
                vector = item_data.get("embedding")
                if not isinstance(index, int) or not isinstance(vector, list):
                    raise OpenAICompatibleUnavailable("embedding item is malformed")
                vector_values = cast(list[object], vector)
                numeric_values = [
                    value for value in vector_values if isinstance(value, (int, float))
                ]
                if not numeric_values or len(numeric_values) != len(vector_values):
                    raise OpenAICompatibleUnavailable("embedding vector is malformed")
                by_index[index] = [float(value) for value in numeric_values]
            if set(by_index) != set(range(len(requests))):
                raise OpenAICompatibleUnavailable("embedding indexes are incomplete")
            return tuple(
                EmbeddingResult(
                    request.item_id,
                    tuple(by_index[index]),
                    self._model_id,
                    VersionTrace(
                        model_id=self._model_id,
                        model_config_hash=self._config_hash,
                        schema_version=request.schema_version,
                        knowledge_snapshot_id=None,
                        pipeline_version=request.pipeline_version,
                        provider=self._provider,
                    ),
                )
                for index, request in enumerate(requests)
            )
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise OpenAICompatibleUnavailable("embedding generation failed") from error


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OpenAICompatibleUnavailable(f"{label} is malformed")
    return cast(dict[str, Any], value)


def _model_ids(payload: dict[str, Any]) -> set[str]:
    raw_models = payload.get("data")
    if not isinstance(raw_models, list):
        raise OpenAICompatibleUnavailable("model list is malformed")
    model_items = cast(list[object], raw_models)
    return {
        str(cast(dict[str, Any], item).get("id"))
        for item in model_items
        if isinstance(item, dict) and cast(dict[str, Any], item).get("id")
    }


def _parse_json_content(
    content: object, output_schema: dict[str, object] | None = None
) -> dict[str, object]:
    if isinstance(content, dict):
        return cast(dict[str, object], content)
    if not isinstance(content, str):
        raise OpenAICompatibleUnavailable("LLM content is not JSON text")
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").removeprefix("json").removesuffix("```").strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise OpenAICompatibleUnavailable("LLM JSON root must be an object")
    result = cast(dict[str, object], parsed)
    if output_schema is not None:
        raw_properties = output_schema.get("properties")
        expected_keys: set[str] = (
            {str(key) for key in cast(dict[str, object], raw_properties)}
            if isinstance(raw_properties, dict)
            else set()
        )
        if expected_keys and not (expected_keys & result.keys()) and len(result) == 1:
            wrapped = next(iter(result.values()))
            if isinstance(wrapped, dict):
                result = cast(dict[str, object], wrapped)
    return result
