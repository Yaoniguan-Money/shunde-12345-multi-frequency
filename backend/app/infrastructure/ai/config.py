"""Explicit, auditable configuration for local, remote and hybrid model adapters."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Final

from pydantic import SecretStr

from backend.app.config import Settings
from backend.app.domain.types import ProviderMode

_DEFAULT_LOCAL_BASE_URL: Final = "http://127.0.0.1:11434"


class ProviderConfigurationError(ValueError):
    """The selected provider mode is not fully and explicitly configured."""


@dataclass(frozen=True, slots=True)
class ProviderEndpoint:
    provider: str
    base_url: str
    model_id: str
    timeout_seconds: float
    concurrency: int
    api_key: SecretStr | None = None

    def config_hash(self) -> str:
        key_fingerprint = None
        if self.api_key is not None:
            key_fingerprint = sha256(self.api_key.get_secret_value().encode("utf-8")).hexdigest()
        payload = "|".join(
            (
                self.provider,
                self.base_url.rstrip("/"),
                self.model_id,
                str(self.timeout_seconds),
                str(self.concurrency),
                key_fingerprint or "no-key",
            )
        )
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AIProviderPlan:
    mode: ProviderMode
    local_llm: ProviderEndpoint | None
    remote_llm: ProviderEndpoint | None
    local_embedding: ProviderEndpoint | None
    remote_embedding: ProviderEndpoint | None
    hybrid_policy: str


def build_provider_plan(
    settings: Settings,
    *,
    llm_model_override: str | None = None,
    embedding_model_override: str | None = None,
) -> AIProviderPlan:
    mode = settings.ai_provider_mode
    timeout = settings.model_timeout_seconds
    concurrency = settings.model_concurrency
    if timeout <= 0:
        raise ProviderConfigurationError("model timeout must be positive")
    if concurrency < 1:
        raise ProviderConfigurationError("model concurrency must be positive")
    if settings.ai_hybrid_policy != "explicit-route-local-default":
        raise ProviderConfigurationError(
            "only the explicit-route-local-default hybrid policy is supported"
        )
    if settings.ai_local_embedding_protocol not in {"ollama", "openai"}:
        raise ProviderConfigurationError("local embedding protocol must be ollama or openai")

    local_needed = mode in {ProviderMode.LOCAL, ProviderMode.HYBRID}
    remote_needed = mode in {ProviderMode.REMOTE, ProviderMode.HYBRID}

    local_llm = _endpoint(
        provider="local-openai-compatible",
        base_url=str(
            settings.ai_local_llm_base_url or settings.model_api_base_url or _DEFAULT_LOCAL_BASE_URL
        ),
        model_id=llm_model_override or settings.ai_local_llm_model_id or settings.llm_model_id,
        timeout=timeout,
        concurrency=concurrency,
        required=local_needed,
        label="local LLM",
    )
    local_embedding = _endpoint(
        provider=(
            "local-openai-compatible"
            if settings.ai_local_embedding_protocol == "openai"
            else "local-ollama"
        ),
        base_url=str(
            settings.ai_local_embedding_base_url
            or settings.embedding_api_base_url
            or settings.model_api_base_url
            or _DEFAULT_LOCAL_BASE_URL
        ),
        model_id=embedding_model_override
        or settings.ai_local_embedding_model_id
        or settings.embedding_model_id,
        timeout=timeout,
        concurrency=concurrency,
        required=local_needed,
        label="local embedding",
    )

    remote_base_url = str(settings.ai_remote_base_url) if settings.ai_remote_base_url else None
    remote_key = settings.ai_remote_api_key
    remote_llm = _endpoint(
        provider="remote-openai-compatible",
        base_url=remote_base_url,
        model_id=settings.ai_remote_llm_model_id,
        timeout=timeout,
        concurrency=concurrency,
        api_key=remote_key,
        required=remote_needed,
        label="remote LLM",
    )
    remote_embedding = _endpoint(
        provider="remote-openai-compatible",
        base_url=remote_base_url,
        model_id=settings.ai_remote_embedding_model_id,
        timeout=timeout,
        concurrency=concurrency,
        api_key=remote_key,
        required=remote_needed,
        label="remote embedding",
    )
    return AIProviderPlan(
        mode=mode,
        local_llm=local_llm,
        remote_llm=remote_llm,
        local_embedding=local_embedding,
        remote_embedding=remote_embedding,
        hybrid_policy=settings.ai_hybrid_policy,
    )


def _endpoint(
    *,
    provider: str,
    base_url: str | None,
    model_id: str | None,
    timeout: float,
    concurrency: int,
    required: bool,
    label: str,
    api_key: SecretStr | None = None,
) -> ProviderEndpoint | None:
    if not required:
        return None
    if not base_url or not model_id:
        raise ProviderConfigurationError(f"{label} requires base_url and model_id")
    if provider.startswith("remote") and api_key is None:
        raise ProviderConfigurationError(
            f"{label} requires an API key from environment configuration"
        )
    return ProviderEndpoint(
        provider=provider,
        base_url=base_url,
        model_id=model_id,
        timeout_seconds=timeout,
        concurrency=concurrency,
        api_key=api_key,
    )
