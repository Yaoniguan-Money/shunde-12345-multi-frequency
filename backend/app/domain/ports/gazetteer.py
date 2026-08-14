from typing import Protocol

from backend.app.domain.types import EntityCandidateSet, GazetteerHealth, GazetteerSnapshot


class GazetteerProvider(Protocol):
    async def health(self) -> GazetteerHealth: ...

    async def snapshot(self) -> GazetteerSnapshot: ...

    async def lookup_many(self, mentions: tuple[str, ...]) -> tuple[EntityCandidateSet, ...]: ...


class MentionResolver(Protocol):
    """Resolve a batch against a runtime snapshot and optional knowledge source."""

    async def resolve_many(self, mentions: tuple[str, ...]) -> tuple[EntityCandidateSet, ...]: ...
