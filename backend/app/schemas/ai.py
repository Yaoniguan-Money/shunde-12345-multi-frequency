from datetime import date
from enum import StrEnum
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def _empty_strings() -> list[str]:
    return []


def _empty_ints() -> list[int]:
    return []


def _empty_evidence() -> list["EventEvidenceItem"]:
    return []


def _empty_spans() -> list["EvidenceSpanItem"]:
    return []


class MentionType(StrEnum):
    PLACE = "place"
    ORGANIZATION = "organization"
    ROAD = "road"
    COMMUNITY = "community"
    UNKNOWN = "unknown"


class MentionRole(StrEnum):
    """V3 受控 mention 角色。"""

    FOCAL_PROJECT = "focal_project"
    PLACE = "place"
    RESPONSIBLE_ORGANIZATION = "responsible_organization"
    CONSTRUCTION_ORGANIZATION = "construction_organization"
    DEVELOPER_OWNER = "developer_owner"
    PRODUCT_OR_BRAND = "product_or_brand"
    ROAD_FACILITY = "road_facility"
    UNKNOWN = "unknown"


class ExtractedMention(BaseModel):
    text: str = Field(min_length=1)
    mention_type: MentionType
    role: MentionRole = MentionRole.UNKNOWN
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    canonical_entity_id: UUID | None = None
    resolution_state: str = "unresolved"
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: list[str] = Field(default_factory=_empty_strings)


class EventEvidenceItem(BaseModel):
    """A verbatim quote that can be checked against one segmented raw source."""

    segment_ordinal: int = Field(ge=0)
    # quote 上限放宽到 1000：qwen-plus 实际返回的市民原话引用常超 240 字，
    # 240 限制导致整张工单的 Pydantic 校验失败、研判 job 卡在 processed=0。
    # 1000 既能容纳真实投诉原话，又防止 LLM 返回整段无关文本。
    quote: str = Field(min_length=1, max_length=1000)


class EvidenceSpanItem(BaseModel):
    """字段级 evidence span（V3）。"""

    field_name: str = Field(min_length=1)
    segment_ordinal: int = Field(ge=0)
    quote: str = Field(min_length=1, max_length=1000)


class ClassificationOutput(BaseModel):
    """分类输出合同（V3 §4.3）。

    模型输出不能直接携带自创中文类型。
    最终存储的名称和父路径始终来自 taxonomy。
    """

    classification_node_id: str | None = None
    candidate_node_ids: list[str] = Field(default_factory=_empty_strings)
    decision: str = "unresolved"
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=_empty_strings)
    reason: str | None = None
    provider_profile: str | None = None
    taxonomy_version: str | None = None


class ExtractedEvent(BaseModel):
    event_type: str | None = None
    behavior: str | None = None
    normalized_summary: str = Field(min_length=1)
    # V3 富字段
    current_problem: str | None = None
    current_request: str | None = None
    history_context: str | None = None
    previous_work_order_references: list[str] = Field(default_factory=_empty_strings)
    focal_object_mentions: list[str] = Field(default_factory=_empty_strings)
    responsible_party_mentions: list[str] = Field(default_factory=_empty_strings)
    location_mentions: list[str] = Field(default_factory=_empty_strings)
    occurrence_interval_start: date | None = None
    occurrence_interval_end: date | None = None
    evidence_spans: list[EvidenceSpanItem] = Field(default_factory=_empty_spans)
    unknown_fields: list[str] = Field(default_factory=_empty_strings)
    # V2 兼容字段
    location_signals: list[str] = Field(default_factory=_empty_strings)
    time_signals: list[str] = Field(default_factory=_empty_strings)
    mention_indexes: list[int] = Field(default_factory=_empty_ints)
    evidence: list[EventEvidenceItem] = Field(default_factory=_empty_evidence)
    # V3 分类输出
    classification: ClassificationOutput | None = None

    @field_validator(
        "previous_work_order_references",
        "focal_object_mentions",
        "responsible_party_mentions",
        "location_mentions",
        "unknown_fields",
        "location_signals",
        "time_signals",
        mode="before",
    )
    @classmethod
    def discard_non_string_mentions(cls, value: object) -> object:
        """Drop malformed numeric/object mentions instead of fabricating entities."""
        if not isinstance(value, list):
            return []
        items = cast(list[object], value)
        return [item.strip() for item in items if isinstance(item, str) and item.strip()]


class UnderstandingTrace(BaseModel):
    provider: str | None = None
    model_id: str | None = None
    model_config_hash: str | None = None
    schema_version: str = "understanding.v3"
    knowledge_snapshot_id: UUID | None = None
    pipeline_version: str


class WorkOrderUnderstanding(BaseModel):
    current_complaint: str | None = None
    historical_context: str | None = None
    department_reply: str | None = None
    current_request: str | None = None
    mentions: list[ExtractedMention] = Field(default_factory=lambda: list[ExtractedMention]())
    events: list[ExtractedEvent] = Field(default_factory=lambda: list[ExtractedEvent]())
    trace: UnderstandingTrace | None = None


class SameEventEvidenceResponse(BaseModel):
    same_entity: bool | None = None
    same_location: bool | None = None
    same_issue: bool | None = None
    time_compatible: bool | None = None
    contradictions: list[str] = Field(default_factory=_empty_strings)


class SameEventResponse(BaseModel):
    same_event: bool
    decision_status: Literal["resolved", "ambiguous", "unresolved"] = "resolved"
    confidence: float = Field(ge=0, le=1)
    evidence: SameEventEvidenceResponse
    evidence_refs: list[str] = Field(default_factory=_empty_strings)
