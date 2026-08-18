"""Candidate retrieval, remote SameEvent decisions and consistent clusters."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from backend.app.domain.ports.analysis import CandidateRetriever, SameEventMatcher
from backend.app.domain.ports.repositories import EventGraphRepository, EventRepository
from backend.app.domain.services.clustering import EventClusterBuilder
from backend.app.domain.types import (
    EventForMatching,
    EventInstanceId,
    EventMatchEdgeRecord,
    RetrievalQuery,
    SameEventDecision,
)


@dataclass(frozen=True, slots=True)
class EventGraphRunResult:
    run_id: UUID
    decisions: tuple[EventMatchEdgeRecord, ...]
    cluster_ids: tuple[UUID, ...]


EventGraphProgress = Callable[[str, dict[str, object]], Awaitable[None]]


class EventGraphService:
    def __init__(
        self,
        events: EventRepository,
        graph: EventGraphRepository,
        retriever: CandidateRetriever,
        matcher: SameEventMatcher,
        *,
        pipeline_version: str = "demo-event-graph.v1",
        schema_version: str = "same-event.v1",
        concurrency: int = 4,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be positive")
        self._events = events
        self._graph = graph
        self._retriever = retriever
        self._matcher = matcher
        self._pipeline_version = pipeline_version
        self._schema_version = schema_version
        self._concurrency = concurrency

    async def run(
        self,
        event_ids: tuple[EventInstanceId, ...],
        *,
        run_id: UUID,
        candidate_limit: int = 10,
        progress: EventGraphProgress | None = None,
    ) -> EventGraphRunResult:
        if not event_ids:
            raise ValueError("at least one event is required")
        if candidate_limit < 1:
            raise ValueError("candidate_limit must be positive")
        loaded_events: list[EventForMatching] = []
        for event_id, event in zip(
            event_ids,
            await asyncio.gather(*(self._events.get_for_matching(value) for value in event_ids)),
            strict=True,
        ):
            if event is None:
                raise LookupError(f"event not found: {event_id}")
            loaded_events.append(event)
        events = tuple(loaded_events)
        events_by_id = {event.event_id: event for event in events}
        selected_ids = {event.event_id for event in events}
        if progress is not None:
            await progress("retrieval", {"event_count": len(events)})
        existing_decisions = await self._graph.list_match_edges(run_id)
        existing_pairs = {
            tuple(sorted((edge.left_event_id, edge.right_event_id), key=str))
            for edge in existing_decisions
        }
        seen_pairs: set[tuple[EventInstanceId, EventInstanceId]] = set()
        retrieval_semaphore = asyncio.Semaphore(self._concurrency)

        async def retrieve(event: EventForMatching):
            async with retrieval_semaphore:
                return await self._retriever.retrieve(
                    RetrievalQuery(
                        event_id=event.event_id,
                        work_order_id=event.work_order_id,
                        entity_ids=event.entity_ids,
                        location_signals=event.location_signals,
                        event_type=event.event_type,
                        text=event.normalized_summary,
                        limit=candidate_limit,
                    )
                )

        candidate_sets = await asyncio.gather(*(retrieve(event) for event in events))
        save_candidate = cast(
            Callable[..., Awaitable[object]] | None,
            getattr(self._graph, "save_candidate", None),
        )
        if callable(save_candidate):
            for event, candidates in zip(events, candidate_sets, strict=True):
                for rank, candidate in enumerate(candidates, start=1):
                    await save_candidate(
                        run_id,
                        event_id=event.event_id,
                        candidate=candidate,
                        retrieval_rank=rank,
                        pipeline_version=self._pipeline_version,
                        schema_version=self._schema_version,
                    )
        pairs: list[tuple[EventInstanceId, EventInstanceId]] = []
        for event, candidates in zip(events, candidate_sets, strict=True):
            for candidate in candidates:
                if candidate.event_id not in selected_ids:
                    continue
                candidate_event = events_by_id[candidate.event_id]
                if candidate_event.work_order_id == event.work_order_id:
                    continue
                left_event_id, right_event_id = sorted(
                    (event.event_id, candidate.event_id), key=str
                )
                pair: tuple[EventInstanceId, EventInstanceId] = (
                    left_event_id,
                    right_event_id,
                )
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                if pair in existing_pairs:
                    continue
                pairs.append(pair)

        if progress is not None:
            await progress(
                "matching",
                {
                    "candidate_pair_count": len(seen_pairs),
                    "match_edge_count": len(existing_decisions),
                },
            )

        match_semaphore = asyncio.Semaphore(self._concurrency)

        async def match(
            pair: tuple[EventInstanceId, EventInstanceId],
        ) -> EventMatchEdgeRecord:
            async with match_semaphore:
                decision = await self._matcher.match(pair[0], pair[1])
                edge = _edge(pair[0], pair[1], decision)
                await self._graph.save_match_edge(
                    run_id,
                    edge,
                    pipeline_version=self._pipeline_version,
                    schema_version=self._schema_version,
                )
                return edge

        if pairs:
            tasks = [asyncio.create_task(match(pair)) for pair in pairs]
            try:
                await asyncio.gather(*tasks)
            except BaseException:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
        decisions = list(await self._graph.list_match_edges(run_id))
        if progress is not None:
            await progress(
                "clustering",
                {
                    "candidate_pair_count": len(seen_pairs),
                    "match_edge_count": len(decisions),
                },
            )
        positive = tuple(edge for edge in decisions if edge.same_event)
        proposals = EventClusterBuilder().build(events, positive)
        cluster_ids: list[UUID] = []
        for proposal in proposals:
            member_events = [events_by_id[event_id] for event_id in proposal.members]
            trace = next(
                edge.trace
                for edge in positive
                if set(proposal.members) & {edge.left_event_id, edge.right_event_id}
            )
            name = _cluster_name(member_events)
            evidence = {
                **proposal.evidence,
                "member_event_ids": [str(event.event_id) for event in member_events],
                "member_work_order_ids": [str(event.work_order_id) for event in member_events],
                "event_types": sorted(
                    {event.event_type for event in member_events if event.event_type}
                ),
                "locations": sorted(
                    {signal for event in member_events for signal in event.location_signals}
                ),
            }
            cluster_ids.append(
                await self._graph.save_cluster(
                    run_id,
                    proposal.members,
                    name=name,
                    confidence=proposal.confidence,
                    evidence=evidence,
                    trace=trace,
                    pipeline_version=self._pipeline_version,
                    schema_version=self._schema_version,
                )
            )
        return EventGraphRunResult(run_id, tuple(decisions), tuple(cluster_ids))


def _edge(
    left_event_id: EventInstanceId,
    right_event_id: EventInstanceId,
    decision: SameEventDecision,
) -> EventMatchEdgeRecord:
    return EventMatchEdgeRecord(
        left_event_id=left_event_id,
        right_event_id=right_event_id,
        same_event=decision.same_event,
        confidence=decision.confidence,
        evidence=decision.evidence,
        trace=decision.trace,
        decision_status=decision.decision_status,
    )


def _cluster_name(events: list[EventForMatching]) -> str:
    summary = max(events, key=lambda event: len(event.normalized_summary)).normalized_summary
    return summary[:512]
