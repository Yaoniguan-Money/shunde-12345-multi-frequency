from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class SegmentType(StrEnum):
    COMPLAINT = "complaint"
    HISTORY = "history"
    DEPARTMENT_REPLY = "department_reply"
    CURRENT_REQUEST = "current_request"


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
class EventEvidence:
    segment_ordinal: int
    segment_type: str
    quote: str
    start_offset: int
    end_offset: int


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
