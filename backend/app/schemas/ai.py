from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


def _empty_strings() -> list[str]:
    return []


def _empty_ints() -> list[int]:
    return []


class MentionType(StrEnum):
    PLACE = "place"
    ORGANIZATION = "organization"
    ROAD = "road"
    COMMUNITY = "community"
    UNKNOWN = "unknown"


class ExtractedMention(BaseModel):
    text: str = Field(min_length=1)
    mention_type: MentionType
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    canonical_entity_id: UUID | None = None
    resolution_state: str = "unresolved"
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: list[str] = Field(default_factory=_empty_strings)


class ExtractedEvent(BaseModel):
    event_type: str | None = None
    normalized_summary: str = Field(min_length=1)
    location_signals: list[str] = Field(default_factory=_empty_strings)
    mention_indexes: list[int] = Field(default_factory=_empty_ints)


class UnderstandingTrace(BaseModel):
    model_id: str | None = None
    model_config_hash: str | None = None
    schema_version: str = "understanding.v1"
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
