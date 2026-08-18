import json
from typing import cast

import httpx
import pytest
from pydantic import SecretStr

from backend.app.application.services.provider_profiles import ProviderProfileService
from backend.app.config import Settings
from backend.app.domain.types import (
    EmbeddingRequest,
    LLMRequest,
    LLMResult,
    ProviderMode,
    ProviderRoute,
    VersionTrace,
)
from backend.app.infrastructure.ai.config import ProviderConfigurationError, build_provider_plan
from backend.app.infrastructure.ai.factory import (
    ExplicitRoutingPolicy,
    ProviderRoutingError,
    RoutedLLMProvider,
)
from backend.app.infrastructure.ai.local import OpenAICompatibleLLMProvider
from backend.app.infrastructure.ai.remote import (
    RemoteOpenAICompatibleEmbeddingProvider,
    RemoteOpenAICompatibleLLMProvider,
)


def _request(route: ProviderRoute = ProviderRoute.AUTO) -> LLMRequest:
    return LLMRequest(
        request_id="provider-test",
        prompt="return a JSON object",
        output_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
        },
        route=route,
    )


class _RecordingLLM:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.calls = 0

    async def generate_batch(self, requests: tuple[LLMRequest, ...]) -> tuple[LLMResult, ...]:
        self.calls += 1
        return tuple(
            LLMResult(
                request.request_id,
                {"provider": self.provider},
                VersionTrace(self.provider, "config", "schema", None, "pipeline", self.provider),
            )
            for request in requests
        )


@pytest.mark.asyncio
async def test_remote_openai_compatible_contract_keeps_key_out_of_trace() -> None:
    secret = "test-secret-do-not-log"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {secret}"
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "remote-model"}]})
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"WorkOrderUnderstanding":{"ok":true}}'}}]
                },
            )
        return httpx.Response(404)

    provider = RemoteOpenAICompatibleLLMProvider(
        "https://remote.example.test",
        "remote-model",
        SecretStr(secret),
        transport=httpx.MockTransport(handler),
    )

    assert await provider.health() == "remote-model"
    result = (await provider.generate_batch((_request(),)))[0]
    assert result.structured_output == {"ok": True}
    assert result.trace.provider == "remote-openai-compatible"
    assert secret not in result.trace.model_config_hash


@pytest.mark.asyncio
async def test_remote_openai_compatible_embedding_contract() -> None:
    secret = "embedding-secret-do-not-log"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {secret}"
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "remote-embedding"}]})
        if request.url.path == "/v1/embeddings":
            inputs = request.read().decode("utf-8")
            count = len(json.loads(inputs)["input"])
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": index, "embedding": [1.0, float(index)]} for index in range(count)
                    ]
                },
            )
        return httpx.Response(404)

    provider = RemoteOpenAICompatibleEmbeddingProvider(
        "https://remote.example.test/v1",
        "remote-embedding",
        SecretStr(secret),
        transport=httpx.MockTransport(handler),
    )
    assert await provider.health() == "remote-embedding"
    results = await provider.embed_batch(
        (EmbeddingRequest("a", "one"), EmbeddingRequest("b", "two"))
    )
    assert [result.vector for result in results] == [(1.0, 0.0), (1.0, 1.0)]
    assert all(result.trace is not None for result in results)
    assert secret not in (results[0].trace.model_config_hash if results[0].trace else "")


def test_local_adapter_rejects_public_url() -> None:
    with pytest.raises(ValueError, match="cloud model endpoints"):
        OpenAICompatibleLLMProvider("https://api.example.test", "model")


def test_remote_configuration_requires_explicit_key() -> None:
    settings = Settings(
        ai_provider_mode=ProviderMode.REMOTE,
        ai_remote_base_url="https://remote.example.test",
        ai_remote_llm_model_id="llm",
        ai_remote_embedding_model_id="embedding",
        ai_remote_api_key=None,
    )
    with pytest.raises(ProviderConfigurationError, match="API key"):
        build_provider_plan(settings)


@pytest.mark.asyncio
async def test_cloud_profile_prefers_explicit_flash_model() -> None:
    service = ProviderProfileService(
        Settings(
            ai_provider_mode=ProviderMode.REMOTE,
            ai_remote_base_url="https://remote.example.test/v1",
            ai_remote_llm_model_id="qwen-plus",
            ai_remote_flash_llm_model_id="qwen-flash",
            ai_remote_embedding_model_id="embedding",
            ai_remote_api_key=SecretStr("test-only"),
        )
    )

    profiles = await service.list_profiles()
    cloud = next(profile for profile in profiles if profile.profile_id == "cloud-qwen")

    assert cloud.model_display_name == "qwen-flash"
    assert "qwen-flash" in cloud.configuration_version
    assert "test-only" not in cloud.model_dump_json()


@pytest.mark.asyncio
async def test_deepseek_profile_uses_local_embedding_without_exposing_secret() -> None:
    service = ProviderProfileService(
        Settings(
            ai_provider_mode=ProviderMode.REMOTE,
            ai_remote_base_url="https://remote.example.test/v1",
            ai_remote_llm_model_id="qwen-plus",
            ai_remote_embedding_model_id="embedding",
            ai_remote_api_key=SecretStr("qwen-test-only"),
            ai_deepseek_base_url="https://api.deepseek.example/v1",
            ai_deepseek_llm_model_id="deepseek-v4-flash",
            ai_deepseek_api_key=SecretStr("deepseek-test-only"),
            ai_local_embedding_base_url="http://127.0.0.1:11434",
            ai_local_embedding_model_id="nomic-embed-text",
            ai_local_embedding_protocol="ollama",
        )
    )

    profiles = await service.list_profiles()
    deepseek = next(profile for profile in profiles if profile.profile_id == "cloud-deepseek")

    assert deepseek.model_display_name == "deepseek-v4-flash"
    assert deepseek.llm_deployment_kind == "cloud"
    assert deepseek.embedding_deployment_kind == "local"
    assert deepseek.configured is True
    serialized = deepseek.model_dump_json()
    assert "deepseek-test-only" not in serialized
    assert "qwen-test-only" not in serialized


def test_provider_plan_supports_independent_llm_and_embedding_routes() -> None:
    settings = Settings(
        ai_provider_mode=ProviderMode.HYBRID,
        ai_local_base_url="http://127.0.0.1:11434",
        ai_local_llm_model_id="qwen2.5:3b",
        ai_local_embedding_base_url="http://127.0.0.1:11434",
        ai_local_embedding_model_id="nomic-embed-text",
        ai_local_embedding_protocol="ollama",
        ai_remote_base_url="https://remote.example.test/v1",
        ai_remote_llm_model_id="deepseek-v4-flash",
        ai_remote_embedding_model_id=None,
        ai_remote_api_key=SecretStr("test-only"),
    )

    plan = build_provider_plan(
        settings,
        llm_mode_override=ProviderMode.REMOTE,
        embedding_mode_override=ProviderMode.LOCAL,
    )

    assert plan.llm_mode == ProviderMode.REMOTE
    assert plan.embedding_mode == ProviderMode.LOCAL
    assert plan.remote_llm is not None
    assert plan.local_embedding is not None
    assert plan.local_llm is None
    assert plan.remote_embedding is None


def test_hybrid_policy_cannot_be_silently_changed() -> None:
    settings = Settings(ai_hybrid_policy="confidence-threshold")
    with pytest.raises(ProviderConfigurationError, match="explicit-route-local-default"):
        build_provider_plan(settings)


@pytest.mark.asyncio
async def test_hybrid_routing_is_explicit_and_has_no_cloud_fallback() -> None:
    local = _RecordingLLM("local")
    remote = _RecordingLLM("remote")
    provider = RoutedLLMProvider(
        ProviderMode.HYBRID,
        cast(object, local),
        cast(object, remote),
        ExplicitRoutingPolicy(),
    )

    automatic = (await provider.generate_batch((_request(),)))[0]
    explicit_remote = (await provider.generate_batch((_request(ProviderRoute.REMOTE),)))[0]
    assert automatic.structured_output["provider"] == "local"
    assert explicit_remote.structured_output["provider"] == "remote"
    assert local.calls == 1
    assert remote.calls == 1

    local_only = RoutedLLMProvider(
        ProviderMode.LOCAL,
        cast(object, local),
        cast(object, remote),
        ExplicitRoutingPolicy(),
    )
    with pytest.raises(ProviderRoutingError, match="remote route is disabled"):
        await local_only.generate_batch((_request(ProviderRoute.REMOTE),))
    assert remote.calls == 1
