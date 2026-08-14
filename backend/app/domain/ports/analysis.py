from typing import Protocol

from backend.app.domain.types import (
    ClusterProposal,
    EmbeddingRequest,
    EmbeddingResult,
    EventCandidate,
    EventInstanceId,
    LLMRequest,
    LLMResult,
    RerankRequest,
    RetrievalQuery,
    SameEventDecision,
)


class LLMProvider(Protocol):
    async def generate_batch(self, requests: tuple[LLMRequest, ...]) -> tuple[LLMResult, ...]: ...


class EmbeddingProvider(Protocol):
    async def embed_batch(
        self, requests: tuple[EmbeddingRequest, ...]
    ) -> tuple[EmbeddingResult, ...]: ...


class RerankerProvider(Protocol):
    async def rerank(self, request: RerankRequest) -> tuple[EventCandidate, ...]: ...


class CandidateRetriever(Protocol):
    async def retrieve(self, query: RetrievalQuery) -> tuple[EventCandidate, ...]: ...


class SameEventMatcher(Protocol):
    async def match(
        self, left_event_id: EventInstanceId, right_event_id: EventInstanceId
    ) -> SameEventDecision: ...


class ClusterConsistencyChecker(Protocol):
    async def validate(self, proposal: ClusterProposal) -> ClusterProposal: ...
