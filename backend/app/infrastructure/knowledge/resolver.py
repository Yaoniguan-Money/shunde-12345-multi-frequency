from backend.app.domain.ports.gazetteer import GazetteerProvider
from backend.app.domain.types import (
    EntityCandidate,
    EntityCandidateSet,
    GazetteerSnapshot,
    ResolutionState,
)
from backend.app.infrastructure.knowledge.snapshot import normalize_alias


class RuntimeEntityResolver:
    """Resolve all mentions against one immutable snapshot, then one remote batch call."""

    def __init__(
        self, snapshot: GazetteerSnapshot, remote: GazetteerProvider | None = None
    ) -> None:
        self._snapshot = snapshot
        self._remote = remote
        self._aliases: dict[str, list[EntityCandidate]] = {}
        for entity in snapshot.entities:
            candidate = EntityCandidate(entity, 1.0, ("runtime_alias_snapshot",))
            for alias in (entity.standard_name, *entity.aliases):
                self._aliases.setdefault(normalize_alias(alias), []).append(candidate)

    async def resolve_many(self, mentions: tuple[str, ...]) -> tuple[EntityCandidateSet, ...]:
        resolved: list[EntityCandidateSet | None] = [None] * len(mentions)
        unresolved_indices: list[int] = []
        for index, mention in enumerate(mentions):
            candidates = tuple(self._aliases.get(normalize_alias(mention), ()))
            if candidates:
                state = (
                    ResolutionState.RESOLVED if len(candidates) == 1 else ResolutionState.AMBIGUOUS
                )
                resolved[index] = EntityCandidateSet(mention, state, candidates)
            else:
                unresolved_indices.append(index)
        if unresolved_indices and self._remote is not None:
            remote_results = await self._remote.lookup_many(
                tuple(mentions[index] for index in unresolved_indices)
            )
            for index, result in zip(unresolved_indices, remote_results, strict=True):
                resolved[index] = self._canonicalize_remote_result(result)
        for index in unresolved_indices:
            if resolved[index] is None:
                resolved[index] = EntityCandidateSet(mentions[index], ResolutionState.UNRESOLVED)
        return tuple(result for result in resolved if result is not None)

    def _canonicalize_remote_result(self, result: EntityCandidateSet) -> EntityCandidateSet:
        candidates: list[EntityCandidate] = []
        for candidate in result.candidates:
            local_candidates = tuple(
                self._aliases.get(normalize_alias(candidate.entity.standard_name), ())
            )
            if len(local_candidates) == 1:
                local = local_candidates[0]
                candidates.append(
                    EntityCandidate(
                        local.entity,
                        candidate.confidence,
                        tuple(dict.fromkeys((*candidate.evidence, "runtime_alias_snapshot"))),
                    )
                )
            else:
                candidates.append(candidate)
        state = result.state
        if candidates and len(candidates) == 1:
            state = ResolutionState.RESOLVED
        return EntityCandidateSet(result.mention, state, tuple(candidates))
