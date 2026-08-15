"""Stable read contracts for the demo catalog endpoints."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

AnalysisState = Literal["unprocessed", "analyzed_no_event", "analyzed", "failed"]
ReviewStatus = Literal["pending_review", "confirmed", "rejected"]


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
    resolution_state: str


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
    occurrence_date: date | None


class WorkOrderSummaryResponse(BaseModel):
    work_order_id: UUID
    external_work_order_number: str | None
    source_row_number: int
    raw_title: str | None
    created_at: datetime
    event_count: int
    cluster_count: int
    analysis_state: AnalysisState
    title_tags: list[str]
    is_urgent: bool


class ClusterReferenceResponse(BaseModel):
    cluster_id: UUID
    cluster_name: str
    review_status: str
    handling_status: str


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
    cluster_refs: list[ClusterReferenceResponse]


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
    occurrence_dated_total: int
    occurrence_unknown_total: int


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
    work_order_count: int
    event_count: int
    evidence: dict[str, object]
    trace: TraceResponse | None
    review_status: ReviewStatus
    is_multi_frequency: bool
    is_high_frequency: bool = False
    frequency_window_days: int = Field(default=3, ge=1)
    frequency_work_order_count: int = Field(default=0, ge=0)


class RemovedMemberResponse(BaseModel):
    event: EventResponse | None
    event_instance_id: UUID
    work_order: WorkOrderSummaryResponse | None
    raw_title: str | None
    raw_content: str | None
    correction_id: UUID
    actor_id: str
    reason: str | None
    removed_at: datetime
    can_restore: bool


class ClusterReviewCreate(BaseModel):
    review_status: ReviewStatus
    actor_id: str = Field(min_length=1, max_length=255)
    reason: str | None = Field(default=None, max_length=10000)


class ClusterReviewResponse(BaseModel):
    cluster_id: UUID
    previous_status: str
    review_status: ReviewStatus
    actor_id: str
    reason: str | None
    reviewed_at: datetime


class ClusterListResponse(BaseModel):
    items: list[ClusterSummaryResponse]
    offset: int
    limit: int
    total: int


class ClusterDetailResponse(BaseModel):
    summary: ClusterSummaryResponse
    members: list[EventDetailResponse]
    work_orders: list[WorkOrderDetailResponse]
    edges: list[MatchEdgeResponse]
    handling_history: list["HandlingRecordResponse"]
    human_corrections: list["HumanCorrectionResponse"]
    removed_members: list[RemovedMemberResponse] = Field(
        default_factory=lambda: list[RemovedMemberResponse]()
    )


class HandlingRecordCreate(BaseModel):
    new_status: str = Field(min_length=1, max_length=32)
    actor_id: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    result: str | None = Field(default=None, max_length=10000)
    attachment_references: list[str] = Field(default_factory=list, max_length=50)


class HandlingRecordResponse(BaseModel):
    record_id: UUID
    cluster_id: UUID
    previous_status: str | None
    new_status: str
    actor_id: str
    description: str | None
    result: str | None
    attachment_references: list[str]
    created_at: datetime


class HumanCorrectionCreate(BaseModel):
    correction_type: Literal["remove_member", "confirm_member"]
    event_instance_id: UUID
    actor_id: str = Field(min_length=1, max_length=255)
    reason: str | None = Field(default=None, max_length=10000)


class HumanCorrectionResponse(BaseModel):
    correction_id: UUID
    cluster_id: UUID | None
    work_order_id: UUID | None
    correction_type: str
    actor_id: str
    reason: str | None
    payload: dict[str, object]
    supersedes_correction_id: UUID | None
    created_at: datetime


class HandlingHistoryResponse(BaseModel):
    items: list[HandlingRecordResponse]


class HumanCorrectionHistoryResponse(BaseModel):
    items: list[HumanCorrectionResponse]


ClusterDetailResponse.model_rebuild()
