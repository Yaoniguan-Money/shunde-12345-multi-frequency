"""Prove one explicitly configured remote OpenAI-compatible model call.

The smoke prompt is synthetic and contains no government work-order text. It is
intended for an operator who has deliberately configured the remote provider in
the process environment; it never falls back to local or cloud credentials.
"""

import argparse
import asyncio
import json
import os

from pydantic import SecretStr

from backend.app.config import get_settings
from backend.app.domain.types import LLMRequest
from backend.app.infrastructure.ai.openai_compatible import OpenAICompatibleUnavailable
from backend.app.infrastructure.ai.remote import RemoteOpenAICompatibleLLMProvider


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model")
    return parser.parse_args()


async def main() -> None:
    args = _args()
    settings = get_settings()
    base_url = settings.ai_remote_base_url
    model_id = args.model or settings.ai_remote_llm_model_id
    api_key = settings.ai_remote_api_key
    if base_url is None or not model_id or api_key is None:
        raise RuntimeError(
            "set SHUNDE_AI_REMOTE_BASE_URL, SHUNDE_AI_REMOTE_LLM_MODEL_ID and "
            "SHUNDE_AI_REMOTE_API_KEY in the process environment"
        )
    provider = RemoteOpenAICompatibleLLMProvider(
        str(base_url),
        model_id,
        SecretStr(api_key.get_secret_value()),
        timeout_seconds=settings.model_timeout_seconds,
        concurrency=settings.model_concurrency,
    )
    health_model: str | None = None
    health_error: str | None = None
    try:
        health_model = await provider.health()
    except OpenAICompatibleUnavailable as error:
        # Some hosted OpenAI-compatible services omit GET /v1/models while chat works.
        # Keep the failed health probe visible, then prove the actual chat contract.
        health_error = str(error)
    result = (
        await provider.generate_batch(
            (
                LLMRequest(
                    request_id="remote-provider-smoke",
                    prompt='只输出 JSON：{"ok": true}。不要解释。',
                    output_schema={
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                    },
                    schema_version="remote-smoke.v1",
                    pipeline_version="remote-smoke.v1",
                ),
            )
        )
    )[0]
    print(
        json.dumps(
            {
                "status": "ok",
                "health_model": health_model,
                "health_error": health_error,
                "provider": result.trace.provider,
                "model_id": result.trace.model_id,
                "model_config_hash": result.trace.model_config_hash,
                "structured_keys": sorted(result.structured_output),
                "api_key_logged": False,
                "environment_model_override": bool(os.environ.get("SHUNDE_AI_REMOTE_LLM_MODEL_ID")),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
