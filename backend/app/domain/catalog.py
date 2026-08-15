"""Typed read models for the demo catalog API.

These models intentionally separate immutable raw work orders from derived event
and cluster projections.  The API may expose raw content on an explicit detail
request, but derived fields always retain their own pipeline/model trace.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import UUID

from backend.app.domain.types import VersionTrace


def _empty_object_dict() -> dict[str, object]:
    return {}


HIGH_FREQUENCY_WINDOW_DAYS = 3
HIGH_FREQUENCY_MIN_WORK_ORDERS = 3


def rolling_window_max_distinct_work_orders(
    records: Iterable[tuple[UUID, date | None]],
    *,
    window_days: int = HIGH_FREQUENCY_WINDOW_DAYS,
) -> int:
    """Return the largest dated-work-order count in any calendar window.

    A work order is counted once per window even when the model extracted more
    than one event from it.  Undated events are intentionally excluded: they
    cannot provide evidence for a time-window frequency claim.
    """

    if window_days < 1:
        raise ValueError("window_days must be at least 1")
    dated = tuple(
        (work_order_id, occurrence_date)
        for work_order_id, occurrence_date in records
        if occurrence_date
    )
    if not dated:
        return 0
    dates = sorted({occurrence_date for _, occurrence_date in dated if occurrence_date})
    window_span = timedelta(days=window_days - 1)
    return max(
        len(
            {
                work_order_id
                for work_order_id, occurrence_date in dated
                if start_date <= occurrence_date <= start_date + window_span
            }
        )
        for start_date in dates
    )


def is_high_frequency_work_order_count(count: int) -> bool:
    return count >= HIGH_FREQUENCY_MIN_WORK_ORDERS


@dataclass(frozen=True, slots=True)
class EntityReference:
    entity_id: UUID
    standard_name: str | None
    entity_type: str | None
    resolution_state: str = "resolved"


@dataclass(frozen=True, slots=True)
class CatalogEvent:
    event_id: UUID
    work_order_id: UUID
    ordinal: int
    event_type: str | None
    behavior: str | None
    normalized_summary: str
    entities: tuple[EntityReference, ...]
    location_signals: tuple[str, ...]
    time_signals: tuple[str, ...]
    evidence: tuple[dict[str, object], ...]
    trace: VersionTrace
    occurrence_date: date | None = None


@dataclass(frozen=True, slots=True)
class WorkOrderSummary:
    work_order_id: UUID
    external_work_order_number: str | None
    source_row_number: int
    raw_title: str | None
    created_at: datetime
    event_count: int
    cluster_count: int
    analysis_state: str = "unprocessed"
    title_tags: tuple[str, ...] = ()
    is_urgent: bool = False


@dataclass(frozen=True, slots=True)
class ClusterReference:
    cluster_id: UUID
    cluster_name: str
    review_status: str
    handling_status: str


@dataclass(frozen=True, slots=True)
class WorkOrderDetail:
    summary: WorkOrderSummary
    import_batch_id: UUID
    raw_content: str
    raw_fields: dict[str, object]
    events: tuple[CatalogEvent, ...]
    cluster_refs: tuple[ClusterReference, ...] = ()


@dataclass(frozen=True, slots=True)
class EventDetail:
    event: CatalogEvent
    work_order: WorkOrderSummary
    raw_title: str | None
    raw_content: str


@dataclass(frozen=True, slots=True)
class MatchEdgeView:
    left_event_id: UUID
    right_event_id: UUID
    same_event: bool
    confidence: float
    evidence: dict[str, object]
    trace: VersionTrace


@dataclass(frozen=True, slots=True)
class HandlingRecordView:
    record_id: UUID
    cluster_id: UUID
    previous_status: str | None
    new_status: str
    actor_id: str
    description: str | None
    result: str | None
    attachment_references: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class HumanCorrectionView:
    correction_id: UUID
    cluster_id: UUID | None
    work_order_id: UUID | None
    correction_type: str
    actor_id: str
    reason: str | None
    payload: dict[str, object]
    supersedes_correction_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RemovedClusterMember:
    event: EventDetail | None
    event_instance_id: UUID
    correction_id: UUID
    actor_id: str
    reason: str | None
    removed_at: datetime
    can_restore: bool


@dataclass(frozen=True, slots=True)
class ClusterReviewView:
    cluster_id: UUID
    previous_status: str
    review_status: str
    actor_id: str
    reason: str | None
    reviewed_at: datetime


@dataclass(frozen=True, slots=True)
class ClusterSummary:
    cluster_id: UUID
    name: str
    status: str
    confidence: float
    handling_status: str
    member_count: int
    work_order_count: int
    event_count: int
    evidence: dict[str, object] = field(default_factory=_empty_object_dict)
    trace: VersionTrace | None = None
    review_status: str = "pending_review"
    is_multi_frequency: bool = True
    is_high_frequency: bool = False
    frequency_window_days: int = HIGH_FREQUENCY_WINDOW_DAYS
    frequency_work_order_count: int = 0


@dataclass(frozen=True, slots=True)
class ClusterDetail:
    summary: ClusterSummary
    members: tuple[EventDetail, ...]
    work_orders: tuple[WorkOrderDetail, ...]
    edges: tuple[MatchEdgeView, ...]
    handling_history: tuple[HandlingRecordView, ...] = ()
    human_corrections: tuple[HumanCorrectionView, ...] = ()
    removed_members: tuple[RemovedClusterMember, ...] = ()
