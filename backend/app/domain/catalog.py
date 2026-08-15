"""Typed read models for the demo catalog API.

These models intentionally separate immutable raw work orders from derived event
and cluster projections.  The API may expose raw content on an explicit detail
request, but derived fields always retain their own pipeline/model trace.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from backend.app.domain.types import VersionTrace


def _empty_object_dict() -> dict[str, object]:
    return {}


@dataclass(frozen=True, slots=True)
class EntityReference:
    entity_id: UUID
    standard_name: str | None
    entity_type: str | None


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


@dataclass(frozen=True, slots=True)
class WorkOrderSummary:
    work_order_id: UUID
    external_work_order_number: str | None
    source_row_number: int
    raw_title: str | None
    created_at: datetime
    event_count: int
    cluster_count: int


@dataclass(frozen=True, slots=True)
class WorkOrderDetail:
    summary: WorkOrderSummary
    import_batch_id: UUID
    raw_content: str
    raw_fields: dict[str, object]
    events: tuple[CatalogEvent, ...]


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


@dataclass(frozen=True, slots=True)
class ClusterDetail:
    summary: ClusterSummary
    members: tuple[EventDetail, ...]
    work_orders: tuple[WorkOrderDetail, ...]
    edges: tuple[MatchEdgeView, ...]
    handling_history: tuple[HandlingRecordView, ...] = ()
    human_corrections: tuple[HumanCorrectionView, ...] = ()
