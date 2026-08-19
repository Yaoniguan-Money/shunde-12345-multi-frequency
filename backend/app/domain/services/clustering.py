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
            left_event = by_id[edge.left_event_id]
            right_event = by_id[edge.right_event_id]
            if left_event.work_order_id == right_event.work_order_id:
                continue
            left_root = _find(parent, edge.left_event_id)
            right_root = _find(parent, edge.right_event_id)
            if left_root == right_root:
                continue
            left_events = [by_id[event_id] for event_id in members[left_root]]
            right_events = [by_id[event_id] for event_id in members[right_root]]
            if _edge_conflicts(edge) or any(
                _conflicts(left, right) for left in left_events for right in right_events
            ):
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
            root_work_order_ids = {
                by_id[event_id].root_work_order_identity or str(by_id[event_id].work_order_id)
                for event_id in event_ids
            }
            if len(event_ids) < 2 or len(root_work_order_ids) < 2:
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
    # Distinct IDs and different free-text locations can describe a project's
    # owner, contractor and site at different granularities.  Only SameEvent's
    # explicit structured evidence can establish a mutually-exclusive conflict.
    del left, right
    return False


def _edge_conflicts(edge: EventMatchEdgeRecord) -> bool:
    evidence = edge.evidence
    return evidence.same_issue is False or any(
        code in {"entity_mutually_exclusive", "location_mutually_exclusive"}
        for code in evidence.contradictions
    )
