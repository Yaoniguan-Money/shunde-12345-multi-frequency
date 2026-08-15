"""Composition root for explicit local/remote/hybrid provider routing."""

from dataclasses import dataclass
from typing import Protocol, cast

from backend.app.config import Settings
from backend.app.domain.ports.analysis import EmbeddingProvider, LLMProvider
from backend.app.domain.types import (
    EmbeddingRequest,
    EmbeddingResult,
    LLMRequest,
    LLMResult,
    ProviderMode,
    ProviderRoute,
)
from backend.app.infrastructure.ai.config import (
    AIProviderPlan,
    ProviderConfigurationError,
    ProviderEndpoint,
    build_provider_plan,
)
from backend.app.infrastructure.ai.local import (
    LocalOpenAICompatibleEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAICompatibleLLMProvider,
)
from backend.app.infrastructure.ai.remote import (
    RemoteOpenAICompatibleEmbeddingProvider,
    RemoteOpenAICompatibleLLMProvider,
)


class ProviderRoutingError(RuntimeError):
    """A request asks for a route that the explicit provider mode disallows."""


class HealthChecked(Protocol):
    async def health(self) -> str: ...


class ExplicitRoutingPolicy:
    """Hybrid policy with no confidence threshold: AUTO always stays local."""

    def choose(self, mode: ProviderMode, route: ProviderRoute) -> ProviderMode:
        if mode is ProviderMode.LOCAL:
            if route is ProviderRoute.REMOTE:
                raise ProviderRoutingError("remote route is disabled while AI_PROVIDER_MODE=local")
            return ProviderMode.LOCAL
        if mode is ProviderMode.REMOTE:
            if route is ProviderRoute.LOCAL:
                raise ProviderRoutingError("local route is disabled while AI_PROVIDER_MODE=remote")
            return ProviderMode.REMOTE
        if route is ProviderRoute.REMOTE:
            return ProviderMode.REMOTE
        return ProviderMode.LOCAL


class RoutedLLMProvider:
    """One stable LLMProvider interface over explicit local/remote adapters."""

    def __init__(
        self,
        mode: ProviderMode,
        local: LLMProvider | None,
        remote: LLMProvider | None,
        policy: ExplicitRoutingPolicy,
    ) -> None:
        self._mode = mode
        self._local = local
        self._remote = remote
        self._policy = policy

    async def health(self) -> dict[str, str]:
        results: dict[str, str] = {}
        for selected, provider in self._providers_for_health():
            if provider is None:
                raise ProviderConfigurationError(f"{selected} LLM provider is not configured")
            health = cast(HealthChecked, provider)
            results[selected] = await health.health()
        return results

    async def generate_batch(self, requests: tuple[LLMRequest, ...]) -> tuple[LLMResult, ...]:
        return await _route_llm_batch(
            requests,
            self._mode,
            self._policy,
            self._local,
            self._remote,
        )

    def _providers_for_health(self) -> tuple[tuple[str, LLMProvider | None], ...]:
        if self._mode is ProviderMode.LOCAL:
            return (("local", self._local),)
        if self._mode is ProviderMode.REMOTE:
            return (("remote", self._remote),)
        return (("local", self._local), ("remote", self._remote))


class RoutedEmbeddingProvider:
    """One stable EmbeddingProvider interface over explicit local/remote adapters."""

    def __init__(
        self,
        mode: ProviderMode,
        local: EmbeddingProvider | None,
        remote: EmbeddingProvider | None,
        policy: ExplicitRoutingPolicy,
    ) -> None:
        self._mode = mode
        self._local = local
        self._remote = remote
        self._policy = policy

    async def health(self) -> dict[str, str]:
        results: dict[str, str] = {}
        for selected, provider in self._providers_for_health():
            if provider is None:
                raise ProviderConfigurationError(f"{selected} embedding provider is not configured")
            health = cast(HealthChecked, provider)
            results[selected] = await health.health()
        return results

    async def embed_batch(
        self, requests: tuple[EmbeddingRequest, ...]
    ) -> tuple[EmbeddingResult, ...]:
        return await _route_embedding_batch(
            requests,
            self._mode,
            self._policy,
            self._local,
            self._remote,
        )

    def _providers_for_health(self) -> tuple[tuple[str, EmbeddingProvider | None], ...]:
        if self._mode is ProviderMode.LOCAL:
            return (("local", self._local),)
        if self._mode is ProviderMode.REMOTE:
            return (("remote", self._remote),)
        return (("local", self._local), ("remote", self._remote))


@dataclass(frozen=True, slots=True)
class AIProviderBundle:
    mode: ProviderMode
    plan: AIProviderPlan
    llm: RoutedLLMProvider
    embeddings: RoutedEmbeddingProvider

    async def health(self) -> dict[str, dict[str, str]]:
        return {"llm": await self.llm.health(), "embedding": await self.embeddings.health()}


def build_provider_bundle(
    settings: Settings,
    *,
    llm_model_override: str | None = None,
    embedding_model_override: str | None = None,
) -> AIProviderBundle:
    plan = build_provider_plan(
        settings,
        llm_model_override=llm_model_override,
        embedding_model_override=embedding_model_override,
    )
    local_llm = _build_local_llm(plan.local_llm)
    remote_llm = _build_remote_llm(plan.remote_llm)
    local_embedding = _build_local_embedding(plan.local_embedding)
    remote_embedding = _build_remote_embedding(plan.remote_embedding)
    policy = ExplicitRoutingPolicy()
    return AIProviderBundle(
        mode=plan.mode,
        plan=plan,
        llm=RoutedLLMProvider(plan.mode, local_llm, remote_llm, policy),
        embeddings=RoutedEmbeddingProvider(plan.mode, local_embedding, remote_embedding, policy),
    )


async def _route_llm_batch(
    requests: tuple[LLMRequest, ...],
    mode: ProviderMode,
    policy: ExplicitRoutingPolicy,
    local: LLMProvider | None,
    remote: LLMProvider | None,
) -> tuple[LLMResult, ...]:
    if not requests:
        return ()
    groups: dict[ProviderMode, list[tuple[int, LLMRequest]]] = {
        ProviderMode.LOCAL: [],
        ProviderMode.REMOTE: [],
    }
    for index, request in enumerate(requests):
        selected = policy.choose(mode, request.route)
        groups[selected].append((index, request))
    outputs: list[LLMResult | None] = [None] * len(requests)
    for selected, grouped in groups.items():
        if not grouped:
            continue
        provider = local if selected is ProviderMode.LOCAL else remote
        if provider is None:
            raise ProviderConfigurationError(f"{selected.value} provider is not configured")
        results = await provider.generate_batch(tuple(request for _, request in grouped))
        if len(results) != len(grouped):
            raise ProviderRoutingError("provider returned an unexpected result count")
        for (index, _), result in zip(grouped, results, strict=True):
            outputs[index] = result
    if any(result is None for result in outputs):
        raise ProviderRoutingError("provider routing left a request without a result")
    return tuple(cast(LLMResult, result) for result in outputs)


async def _route_embedding_batch(
    requests: tuple[EmbeddingRequest, ...],
    mode: ProviderMode,
    policy: ExplicitRoutingPolicy,
    local: EmbeddingProvider | None,
    remote: EmbeddingProvider | None,
) -> tuple[EmbeddingResult, ...]:
    if not requests:
        return ()
    groups: dict[ProviderMode, list[tuple[int, EmbeddingRequest]]] = {
        ProviderMode.LOCAL: [],
        ProviderMode.REMOTE: [],
    }
    for index, request in enumerate(requests):
        selected = policy.choose(mode, request.route)
        groups[selected].append((index, request))
    outputs: list[EmbeddingResult | None] = [None] * len(requests)
    for selected, grouped in groups.items():
        if not grouped:
            continue
        provider = local if selected is ProviderMode.LOCAL else remote
        if provider is None:
            raise ProviderConfigurationError(f"{selected.value} provider is not configured")
        results = await provider.embed_batch(tuple(request for _, request in grouped))
        if len(results) != len(grouped):
            raise ProviderRoutingError("provider returned an unexpected result count")
        for (index, _), result in zip(grouped, results, strict=True):
            outputs[index] = result
    if any(result is None for result in outputs):
        raise ProviderRoutingError("provider routing left a request without a result")
    return tuple(cast(EmbeddingResult, result) for result in outputs)


def _build_local_llm(endpoint: ProviderEndpoint | None) -> LLMProvider | None:
    if endpoint is None:
        return None
    return OpenAICompatibleLLMProvider(
        endpoint.base_url,
        endpoint.model_id,
        timeout_seconds=endpoint.timeout_seconds,
        concurrency=endpoint.concurrency,
    )


def _build_remote_llm(endpoint: ProviderEndpoint | None) -> LLMProvider | None:
    if endpoint is None:
        return None
    if endpoint.api_key is None:
        raise ProviderConfigurationError("remote LLM API key is required")
    return RemoteOpenAICompatibleLLMProvider(
        endpoint.base_url,
        endpoint.model_id,
        endpoint.api_key,
        timeout_seconds=endpoint.timeout_seconds,
        concurrency=endpoint.concurrency,
    )


def _build_local_embedding(endpoint: ProviderEndpoint | None) -> EmbeddingProvider | None:
    if endpoint is None:
        return None
    if endpoint.provider == "local-ollama":
        return OllamaEmbeddingProvider(
            endpoint.base_url,
            endpoint.model_id,
            timeout_seconds=endpoint.timeout_seconds,
        )
    return LocalOpenAICompatibleEmbeddingProvider(
        endpoint.base_url,
        endpoint.model_id,
        timeout_seconds=endpoint.timeout_seconds,
        concurrency=endpoint.concurrency,
    )


def _build_remote_embedding(endpoint: ProviderEndpoint | None) -> EmbeddingProvider | None:
    if endpoint is None:
        return None
    if endpoint.api_key is None:
        raise ProviderConfigurationError("remote embedding API key is required")
    return RemoteOpenAICompatibleEmbeddingProvider(
        endpoint.base_url,
        endpoint.model_id,
        endpoint.api_key,
        timeout_seconds=endpoint.timeout_seconds,
        concurrency=endpoint.concurrency,
    )
