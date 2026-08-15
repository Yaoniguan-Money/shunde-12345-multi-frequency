"""Explicit remote OpenAI-compatible adapters.

These adapters are never selected by default. Their constructors require an API key
and the factory only wires them when ``AI_PROVIDER_MODE=remote`` or ``hybrid``.
"""

import httpx
from pydantic import SecretStr

from backend.app.infrastructure.ai.openai_compatible import (
    OpenAICompatibleChatAdapter,
    OpenAICompatibleEmbeddingAdapter,
)


class RemoteOpenAICompatibleLLMProvider(OpenAICompatibleChatAdapter):
    def __init__(
        self,
        base_url: str,
        model_id: str,
        api_key: SecretStr,
        *,
        timeout_seconds: float = 120.0,
        concurrency: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url,
            model_id,
            provider="remote-openai-compatible",
            allow_public_url=True,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            concurrency=concurrency,
            transport=transport,
        )


class RemoteOpenAICompatibleEmbeddingProvider(OpenAICompatibleEmbeddingAdapter):
    def __init__(
        self,
        base_url: str,
        model_id: str,
        api_key: SecretStr,
        *,
        timeout_seconds: float = 120.0,
        concurrency: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url,
            model_id,
            provider="remote-openai-compatible",
            allow_public_url=True,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            concurrency=concurrency,
            transport=transport,
        )
