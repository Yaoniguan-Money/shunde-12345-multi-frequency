"""Public contracts for the evidence-first intelligent assessment assistant."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

AgentIntent = Literal[
    "search_work_orders",
    "refine_previous",
    "create_workset",
    "export_work_orders",
    "generate_dashboard",
    "preview_batch_action",
]
HandlingStatus = Literal["unhandled", "investigating", "resolved"]
AgentFrequencyFilter = Literal["all", "multi_frequency", "high_frequency"]
AgentPageSize = Literal[20, 50, 100]
AgentAggregation = Literal[
    "none",
    "count",
    "group_by_topic",
    "group_by_status",
    "group_by_location",
]
AgentContextMode = Literal["new_scope", "refine_scope", "reference_results"]
BatchActionType = Literal["add_handling_record", "set_handling_status", "export_csv"]


def _empty_strings() -> list[str]:
    return []


def _empty_uuids() -> list[UUID]:
    return []


def _empty_trace() -> list[dict[str, object]]:
    return []


def _empty_tree_groups() -> list["AgentTreeGroup"]:
    return []


class AgentTimeRange(BaseModel):
    kind: Literal["relative", "absolute"]
    value: str | None = Field(default=None, max_length=32)
    start: datetime | None = None
    end: datetime | None = None


class AgentQueryDSL(BaseModel):
    # Retain the user's wording for vector retrieval.  The remaining slots are
    # controlled query semantics and are not a substitute for this text.
    semantic_query: str | None = Field(default=None, max_length=500)
    intent: AgentIntent = "search_work_orders"
    time_range: AgentTimeRange | None = None
    keywords: list[str] = Field(default_factory=_empty_strings, max_length=8)
    topic: str | None = Field(default=None, max_length=128)
    # Title tags are deterministic catalog facts. They are never inferred from
    # semantic retrieval or a model's guess about urgency.
    title_tag: str | None = Field(default=None, max_length=32)
    aggregation: AgentAggregation = "none"
    context_mode: AgentContextMode = "new_scope"
    # A topic mentioned by the user is a result constraint, not merely a
    # ranking hint.  `keywords` remain broad candidate-recall terms.
    issue_required: bool = False
    entity: str | None = Field(default=None, max_length=128)
    location: str | None = Field(default=None, max_length=128)
    event_type: str | None = Field(default=None, max_length=128)
    handling_status: HandlingStatus | None = None
    cluster_status: str | None = Field(default=None, max_length=32)
    sort: Literal["relevance", "newest", "oldest"] = "relevance"
    limit: int = Field(default=20, ge=1, le=100)
    work_order_ids: list[UUID] = Field(default_factory=_empty_uuids, max_length=100)


class AgentQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    previous_query: str | None = Field(default=None, max_length=500)
    previous_query_snapshot: AgentQueryDSL | None = None
    previous_work_order_ids: list[UUID] = Field(default_factory=_empty_uuids, max_length=100)
    limit: AgentPageSize = 20


class AgentWorkOrderResult(BaseModel):
    work_order_id: UUID
    external_work_order_number: str | None
    title: str | None
    title_tags: list[str]
    is_urgent: bool
    reported_at: datetime | None
    time_label: str
    normalized_summary: str | None
    location: str | None
    event_type: str | None
    handling_status: str
    cluster_ids: list[UUID]
    is_multi_frequency: bool
    is_high_frequency: bool
    retrieval_evidence: list[str]


class AgentTopicGroup(BaseModel):
    label: str
    count: int


class AgentTreeChild(BaseModel):
    """A complete second-level aggregate with navigable example leaves."""

    label: str
    count: int
    work_orders: list[AgentWorkOrderResult]


class AgentTreeGroup(BaseModel):
    """A complete first-level aggregate for one relationship-tree view."""

    label: str
    count: int
    urgent_count: int
    multi_frequency_count: int
    children: list[AgentTreeChild]


class AgentQueryResponse(BaseModel):
    original_query: str
    compiled_query: AgentQueryDSL
    planner_mode: Literal["llm", "rules"]
    answer: str
    disclaimer: str
    total: int
    matched_total: int
    page: int
    page_size: int
    topic_groups: list[AgentTopicGroup]
    handling_groups: list[AgentTopicGroup]
    work_orders: list[AgentWorkOrderResult]
    cluster_ids: list[UUID]
    retrieval_trace: list[dict[str, object]] = Field(default_factory=_empty_trace)


class AgentDrilldown(BaseModel):
    """A deterministic refinement of one already-compiled query scope."""

    topic: str | None = Field(default=None, max_length=128)
    location: str | None = Field(default=None, max_length=256)
    handling_status: HandlingStatus | None = None
    frequency: AgentFrequencyFilter = "all"


class AgentQueryResultsRequest(BaseModel):
    compiled_query: AgentQueryDSL
    page: int = Field(default=1, ge=1)
    page_size: AgentPageSize = 20
    drilldown: AgentDrilldown = Field(default_factory=AgentDrilldown)


class AgentQueryResultsResponse(BaseModel):
    matched_total: int
    page: int
    page_size: int
    items: list[AgentWorkOrderResult]


class AgentExportRequest(BaseModel):
    """Export the complete result set of one already compiled Agent query."""

    original_query: str = Field(min_length=1, max_length=500)
    compiled_query: AgentQueryDSL


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


class WorksetListResponse(BaseModel):
    """Recent durable worksets, ordered for workspace restoration."""

    items: list[WorksetResponse]
    total: int


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
    compiled_query: AgentQueryDSL | None = None
    drilldown: AgentDrilldown | None = None
    title: str = Field(default="临时研判看板", min_length=1, max_length=255)


class AgentInsightBrief(BaseModel):
    """Complete-scope factual briefing assembled only from dashboard aggregates."""

    conclusion: str
    evidence_points: list[str] = Field(default_factory=_empty_strings)
    next_step: str


class DynamicDashboardResponse(BaseModel):
    title: str
    work_order_count: int
    multi_frequency_event_count: int
    multi_frequency_work_order_count: int
    high_frequency_event_count: int
    urgent_count: int
    handling_groups: list[AgentTopicGroup]
    topic_groups: list[AgentTopicGroup]
    location_groups: list[AgentTopicGroup]
    topic_tree: list[AgentTreeGroup] = Field(default_factory=_empty_tree_groups)
    location_tree: list[AgentTreeGroup] = Field(default_factory=_empty_tree_groups)
    status_tree: list[AgentTreeGroup] = Field(default_factory=_empty_tree_groups)
    focus_cluster_ids: list[UUID]
    insight_brief: AgentInsightBrief
    disclaimer: str


class WorksetWorkspaceResponse(BaseModel):
    """The durable workspace surface: current members plus real-time aggregates."""

    workset: WorksetResponse
    work_orders: list[AgentWorkOrderResult]
    dashboard: DynamicDashboardResponse
