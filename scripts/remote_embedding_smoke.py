"""Prove the configured remote OpenAI-compatible embedding contract.

The request is synthetic and deliberately contains no government work-order text.
The script reports the real model id and vector dimensions returned by the service;
it never infers dimensions from a model name.
"""

import asyncio
import json

from pydantic import SecretStr

from backend.app.config import get_settings
from backend.app.domain.types import EmbeddingRequest
from backend.app.infrastructure.ai.remote import RemoteOpenAICompatibleEmbeddingProvider


async def main() -> None:
    settings = get_settings()
    base_url = settings.ai_remote_base_url
    model_id = settings.ai_remote_embedding_model_id
    api_key = settings.ai_remote_api_key
    if base_url is None or not model_id or api_key is None:
        raise RuntimeError(
            "set SHUNDE_AI_REMOTE_BASE_URL, SHUNDE_AI_REMOTE_EMBEDDING_MODEL_ID and "
            "SHUNDE_AI_REMOTE_API_KEY in the process environment"
        )
    provider = RemoteOpenAICompatibleEmbeddingProvider(
        str(base_url),
        model_id,
        SecretStr(api_key.get_secret_value()),
        timeout_seconds=settings.model_timeout_seconds,
        concurrency=settings.model_concurrency,
    )
    health_model = await provider.health()
    result = (
        await provider.embed_batch(
            (
                EmbeddingRequest(
                    item_id="remote-embedding-smoke",
                    text="合成测试：同一地点的噪声投诉事件。",
                    schema_version="remote-embedding-smoke.v1",
                    pipeline_version="remote-embedding-smoke.v1",
                ),
            )
        )
    )[0]
    trace = result.trace
    print(
        json.dumps(
            {
                "status": "ok",
                "health_model": health_model,
                "provider": trace.provider if trace else None,
                "model_id": result.model_id,
                "dimensions": len(result.vector),
                "model_config_hash": trace.model_config_hash if trace else None,
                "api_key_logged": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
