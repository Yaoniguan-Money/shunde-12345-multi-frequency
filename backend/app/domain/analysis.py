from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID


class SegmentType(StrEnum):
    COMPLAINT = "complaint"
    HISTORY = "history"
    DEPARTMENT_REPLY = "department_reply"
    CURRENT_REQUEST = "current_request"


class MentionRole(StrEnum):
    """受控 mention 角色（V3）。

    不能把所有专名都塞进地点词典。
    RealityObjectResolver 按对象类型调用不同适配器。
    """

    FOCAL_PROJECT = "focal_project"
    PLACE = "place"
    RESPONSIBLE_ORGANIZATION = "responsible_organization"
    CONSTRUCTION_ORGANIZATION = "construction_organization"
    DEVELOPER_OWNER = "developer_owner"
    PRODUCT_OR_BRAND = "product_or_brand"
    ROAD_FACILITY = "road_facility"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TextSegment:
    segment_type: SegmentType
    text: str
    ordinal: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class ExtractedMention:
    text: str
    mention_type: str
    start_offset: int | None
    end_offset: int | None
    canonical_entity_id: UUID | None
    resolution_state: str
    confidence: float | None
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    """字段级 evidence span（V3）。

    每个关键字段（项目、组织、地点、问题、诉求、日期）
    必须引用原文 evidence span。
    """

    field_name: str
    segment_ordinal: int
    segment_type: str
    quote: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class EventEvidence:
    segment_ordinal: int
    segment_type: str
    quote: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class EventFact:
    """V3 事项结构，替代 v2 的 ExtractedEvent。

    一张工单同时反映不同现实问题时必须拆分。
    每个事项拥有独立分类、对象、地点、诉求和证据。
    """

    event_type: str | None
    behavior: str | None
    normalized_summary: str
    current_problem: str | None
    current_request: str | None
    history_context: str | None
    location_signals: tuple[str, ...]
    time_signals: tuple[str, ...]
    mention_indexes: tuple[int, ...]
    evidence: tuple[EventEvidence, ...] = ()
    evidence_spans: tuple[EvidenceSpan, ...] = ()
    unknown_fields: tuple[str, ...] = ()
    previous_work_order_references: tuple[str, ...] = ()
    occurrence_interval_start: date | None = None
    occurrence_interval_end: date | None = None


@dataclass(frozen=True, slots=True)
class ExtractedEvent:
    event_type: str | None
    behavior: str | None
    normalized_summary: str
    location_signals: tuple[str, ...]
    time_signals: tuple[str, ...]
    mention_indexes: tuple[int, ...]
    evidence: tuple[EventEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class StructuredUnderstanding:
    current_complaint: str | None
    historical_context: str | None
    department_reply: str | None
    current_request: str | None
    mentions: tuple[ExtractedMention, ...]
    events: tuple[ExtractedEvent, ...]
