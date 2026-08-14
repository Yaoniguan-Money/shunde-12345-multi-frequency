"""Local-only model adapters."""

from backend.app.infrastructure.ai.local import (
    LocalModelUnavailable,
    OllamaEmbeddingProvider,
    OpenAICompatibleLLMProvider,
)

__all__ = [
    "LocalModelUnavailable",
    "OllamaEmbeddingProvider",
    "OpenAICompatibleLLMProvider",
]
