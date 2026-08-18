"""Public contracts for the evidence-first intelligent assessment assistant."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

AgentIntent = Literal[
    "search_work_orders",
    "refine_previous",
    "create_workset",
    "generate_dashboard",
    "preview_batch_action",
]
HandlingStatus = Literal["unhandled", "investigating", "resolved"]
BatchActionType = Literal["add_handling_record", "set_handling_status", "export_csv"]


def _empty_strings() -> list[str]:
    return []


def _empty_uuids() -> list[UUID]:
    return []


class AgentTimeRange(BaseModel):
    kind: Literal["relative", "absolute"]
    value: str | None = Field(default=None, max_length=32)
    start: datetime | None = None
    end: datetime | None = None


class AgentQueryDSL(BaseModel):
    intent: AgentIntent = "search_work_orders"
    time_range: AgentTimeRange | None = None
    keywords: list[str] = Field(default_factory=_empty_strings, max_length=8)
    topic: str | None = Field(default=None, max_length=128)
    entity: str | None = Field(default=None, max_length=128)
    location: str | None = Field(default=None, max_length=128)
    event_type: str | None = Field(default=None, max_length=128)
    handling_status: HandlingStatus | None = None
    cluster_status: str | None = Field(default=None, max_length=32)
    sort: Literal["relevance", "newest", "oldest"] = "relevance"
    limit: int = Field(default=20, ge=1, le=50)
    work_order_ids: list[UUID] = Field(default_factory=_empty_uuids, max_length=100)


class AgentQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    previous_query_snapshot: AgentQueryDSL | None = None
    previous_work_order_ids: list[UUID] = Field(default_factory=_empty_uuids, max_length=100)
    limit: int = Field(default=20, ge=1, le=50)


class AgentWorkOrderResult(BaseModel):
    work_order_id: UUID
    external_work_order_number: str | None
    title: str | None
    reported_at: datetime | None
    time_label: str
    normalized_summary: str | None
    location: str | None
    event_type: str | None
    handling_status: str
    cluster_ids: list[UUID]
    is_multi_frequency: bool
    retrieval_evidence: list[str]


class AgentTopicGroup(BaseModel):
    label: str
    count: int


class AgentQueryResponse(BaseModel):
    original_query: str
    compiled_query: AgentQueryDSL
    planner_mode: Literal["llm", "rules"]
    answer: str
    disclaimer: str
    total: int
    topic_groups: list[AgentTopicGroup]
    handling_groups: list[AgentTopicGroup]
    work_orders: list[AgentWorkOrderResult]
    cluster_ids: list[UUID]


class WorksetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    original_query: str = Field(min_length=1, max_length=500)
    query_snapshot: AgentQueryDSL
    work_order_ids: list[UUID] = Field(default_factory=_empty_uuids, max_length=100)
    cluster_ids: list[UUID] = Field(default_factory=_empty_uuids, max_length=100)
    created_by: str = Field(default="demo-operator", min_length=1, max_length=255)


class WorksetResponse(BaseModel):
    id: UUID
    name: str
    original_query: str
    query_snapshot: AgentQueryDSL
    work_order_ids: list[UUID]
    cluster_ids: list[UUID]
    created_at: datetime
    created_by: str
    result_count: int
    metadata: dict[str, object]


class BatchActionPayload(BaseModel):
    action_type: BatchActionType
    new_status: HandlingStatus | None = None
    description: str | None = Field(default=None, max_length=1000)
    result: str | None = Field(default=None, max_length=1000)
    actor_id: str = Field(default="demo-operator", min_length=1, max_length=255)


class BatchActionPreviewResponse(BaseModel):
    preview_id: UUID
    action_type: BatchActionType
    affected_work_order_count: int
    affected_cluster_count: int
    skipped_work_order_count: int
    before_status_counts: dict[str, int]
    after_status: str | None
    message: str


class BatchActionExecuteRequest(BaseModel):
    preview_id: UUID
    actor_id: str = Field(default="demo-operator", min_length=1, max_length=255)


class BatchActionExecuteResponse(BaseModel):
    preview_id: UUID
    action_type: BatchActionType
    executed_work_order_count: int
    audit_action: str
    csv_content: str | None = None


class DynamicDashboardRequest(BaseModel):
    work_order_ids: list[UUID] = Field(default_factory=_empty_uuids, max_length=100)
    cluster_ids: list[UUID] = Field(default_factory=_empty_uuids, max_length=100)
    title: str = Field(default="临时研判看板", min_length=1, max_length=255)


class DynamicDashboardResponse(BaseModel):
    title: str
    work_order_count: int
    multi_frequency_event_count: int
    handling_groups: list[AgentTopicGroup]
    topic_groups: list[AgentTopicGroup]
    location_groups: list[AgentTopicGroup]
    focus_cluster_ids: list[UUID]
    disclaimer: str
