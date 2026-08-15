"""Consistency-aware connected components for positive SameEvent edges."""

from backend.app.domain.types import (
    ClusterProposal,
    EventForMatching,
    EventInstanceId,
    EventMatchEdgeRecord,
)


class EventClusterBuilder:
    """Build clusters without allowing contradictory transitive merges."""

    def build(
        self,
        events: tuple[EventForMatching, ...],
        edges: tuple[EventMatchEdgeRecord, ...],
    ) -> tuple[ClusterProposal, ...]:
        by_id = {event.event_id: event for event in events}
        parent = {event.event_id: event.event_id for event in events}
        members: dict[EventInstanceId, set[EventInstanceId]] = {
            event.event_id: {event.event_id} for event in events
        }
        rejected: list[tuple[EventInstanceId, EventInstanceId]] = []
        accepted_confidence: dict[EventInstanceId, list[float]] = {
            event.event_id: [] for event in events
        }

        for edge in sorted(edges, key=lambda item: item.confidence, reverse=True):
            left_root = _find(parent, edge.left_event_id)
            right_root = _find(parent, edge.right_event_id)
            if left_root == right_root:
                continue
            left_events = [by_id[event_id] for event_id in members[left_root]]
            right_events = [by_id[event_id] for event_id in members[right_root]]
            if any(_conflicts(left, right) for left in left_events for right in right_events):
                rejected.append((edge.left_event_id, edge.right_event_id))
                continue
            if len(members[left_root]) < len(members[right_root]):
                left_root, right_root = right_root, left_root
            parent[right_root] = left_root
            members[left_root].update(members.pop(right_root))
            accepted_confidence[left_root].extend(
                (*accepted_confidence.pop(right_root), edge.confidence)
            )

        proposals: list[ClusterProposal] = []
        for root, event_ids in members.items():
            if len(event_ids) < 2:
                continue
            scores = accepted_confidence.get(root, [])
            proposals.append(
                ClusterProposal(
                    members=tuple(sorted(event_ids, key=str)),
                    rejected_edges=tuple(
                        pair for pair in rejected if pair[0] in event_ids or pair[1] in event_ids
                    ),
                    confidence=min(scores) if scores else 0.0,
                    evidence={
                        "consistency": "complete_link_guard",
                        "rejected_edges": [
                            [str(left), str(right)]
                            for left, right in rejected
                            if left in event_ids or right in event_ids
                        ],
                    },
                )
            )
        return tuple(proposals)


def _find(
    parent: dict[EventInstanceId, EventInstanceId], value: EventInstanceId
) -> EventInstanceId:
    root = value
    while parent[root] != root:
        root = parent[root]
    while parent[value] != value:
        next_value = parent[value]
        parent[value] = root
        value = next_value
    return root


def _conflicts(left: EventForMatching, right: EventForMatching) -> bool:
    if left.entity_ids and right.entity_ids and set(left.entity_ids).isdisjoint(right.entity_ids):
        return True
    if (
        left.location_signals
        and right.location_signals
        and _normalize(left.location_signals).isdisjoint(_normalize(right.location_signals))
    ):
        return True
    return bool(left.event_type and right.event_type and left.event_type != right.event_type)


def _normalize(values: tuple[str, ...]) -> set[str]:
    return {"".join(value.split()).casefold() for value in values if value.strip()}
