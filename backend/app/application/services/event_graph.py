"""Candidate retrieval, remote SameEvent decisions and consistent clusters."""

from dataclasses import dataclass
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
    ) -> None:
        self._events = events
        self._graph = graph
        self._retriever = retriever
        self._matcher = matcher
        self._pipeline_version = pipeline_version
        self._schema_version = schema_version

    async def run(
        self,
        event_ids: tuple[EventInstanceId, ...],
        *,
        candidate_limit: int = 10,
    ) -> EventGraphRunResult:
        if not event_ids:
            raise ValueError("at least one event is required")
        if candidate_limit < 1:
            raise ValueError("candidate_limit must be positive")
        loaded_events: list[EventForMatching] = []
        for event_id in event_ids:
            event = await self._events.get_for_matching(event_id)
            if event is None:
                raise LookupError(f"event not found: {event_id}")
            loaded_events.append(event)
        events = tuple(loaded_events)
        events_by_id = {event.event_id: event for event in events}
        selected_ids = {event.event_id for event in events}
        _job_id, run_id = await self._graph.start_run(
            pipeline_version=self._pipeline_version,
            schema_version=self._schema_version,
        )
        decisions: list[EventMatchEdgeRecord] = []
        seen_pairs: set[tuple[EventInstanceId, EventInstanceId]] = set()
        for event in events:
            candidates = await self._retriever.retrieve(
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
                decision = await self._matcher.match(pair[0], pair[1])
                edge = _edge(pair[0], pair[1], decision)
                await self._graph.save_match_edge(
                    run_id,
                    edge,
                    pipeline_version=self._pipeline_version,
                    schema_version=self._schema_version,
                )
                decisions.append(edge)
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
        await self._graph.finish_run(
            run_id,
            {
                "events": len(events),
                "candidate_pairs": len(decisions),
                "positive_edges": len(positive),
                "clusters": len(cluster_ids),
            },
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
    )


def _cluster_name(events: list[EventForMatching]) -> str:
    summary = max(events, key=lambda event: len(event.normalized_summary)).normalized_summary
    return summary[:512]
