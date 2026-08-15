"""Auditable local/remote model adapters and explicit routing composition."""

from backend.app.infrastructure.ai.config import (
    AIProviderPlan,
    ProviderConfigurationError,
    ProviderEndpoint,
    build_provider_plan,
)
from backend.app.infrastructure.ai.factory import (
    AIProviderBundle,
    ProviderRoutingError,
    build_provider_bundle,
)
from backend.app.infrastructure.ai.local import (
    LocalModelUnavailable,
    LocalOpenAICompatibleEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAICompatibleLLMProvider,
)
from backend.app.infrastructure.ai.remote import (
    RemoteOpenAICompatibleEmbeddingProvider,
    RemoteOpenAICompatibleLLMProvider,
)

__all__ = [
    "AIProviderBundle",
    "AIProviderPlan",
    "LocalModelUnavailable",
    "LocalOpenAICompatibleEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "OpenAICompatibleLLMProvider",
    "ProviderConfigurationError",
    "ProviderEndpoint",
    "ProviderRoutingError",
    "RemoteOpenAICompatibleEmbeddingProvider",
    "RemoteOpenAICompatibleLLMProvider",
    "build_provider_bundle",
    "build_provider_plan",
]
