"""Stable read contracts for the demo catalog endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TraceResponse(BaseModel):
    provider: str | None
    model_id: str | None
    model_config_hash: str | None
    schema_version: str
    knowledge_snapshot_id: UUID | None
    pipeline_version: str


class EntityReferenceResponse(BaseModel):
    entity_id: UUID
    standard_name: str | None
    entity_type: str | None


class EventResponse(BaseModel):
    event_id: UUID
    work_order_id: UUID
    ordinal: int
    event_type: str | None
    behavior: str | None
    normalized_summary: str
    entities: list[EntityReferenceResponse]
    location_signals: list[str]
    time_signals: list[str]
    evidence: list[dict[str, object]]
    trace: TraceResponse


class WorkOrderSummaryResponse(BaseModel):
    work_order_id: UUID
    external_work_order_number: str | None
    source_row_number: int
    raw_title: str | None
    created_at: datetime
    event_count: int
    cluster_count: int


class WorkOrderListResponse(BaseModel):
    items: list[WorkOrderSummaryResponse]
    offset: int
    limit: int
    total: int


class WorkOrderDetailResponse(BaseModel):
    summary: WorkOrderSummaryResponse
    import_batch_id: UUID
    raw_content: str
    raw_fields: dict[str, object]
    events: list[EventResponse]


class EventDetailResponse(BaseModel):
    event: EventResponse
    work_order: WorkOrderSummaryResponse
    raw_title: str | None
    raw_content: str


class EventListResponse(BaseModel):
    items: list[EventDetailResponse]
    offset: int
    limit: int
    total: int


class MatchEdgeResponse(BaseModel):
    left_event_id: UUID
    right_event_id: UUID
    same_event: bool
    confidence: float = Field(ge=0, le=1)
    evidence: dict[str, object]
    trace: TraceResponse


class ClusterSummaryResponse(BaseModel):
    cluster_id: UUID
    name: str
    status: str
    confidence: float = Field(ge=0, le=1)
    handling_status: str
    member_count: int
    evidence: dict[str, object]
    trace: TraceResponse | None


class ClusterListResponse(BaseModel):
    items: list[ClusterSummaryResponse]
    offset: int
    limit: int
    total: int


class ClusterDetailResponse(BaseModel):
    summary: ClusterSummaryResponse
    members: list[EventDetailResponse]
    edges: list[MatchEdgeResponse]
