from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import NewType
from uuid import UUID

EntityId = NewType("EntityId", UUID)
WorkOrderId = NewType("WorkOrderId", UUID)
EventInstanceId = NewType("EventInstanceId", UUID)
EventClusterId = NewType("EventClusterId", UUID)
JobId = NewType("JobId", UUID)


def _empty_object_dict() -> dict[str, object]:
    return {}


class ResolutionState(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class ProviderMode(StrEnum):
    LOCAL = "local"
    REMOTE = "remote"
    HYBRID = "hybrid"


class ProviderRoute(StrEnum):
    AUTO = "auto"
    LOCAL = "local"
    REMOTE = "remote"


@dataclass(frozen=True, slots=True)
class VersionTrace:
    model_id: str | None
    model_config_hash: str | None
    schema_version: str
    knowledge_snapshot_id: UUID | None
    pipeline_version: str
    provider: str | None = None


@dataclass(frozen=True, slots=True)
class RawWorkOrderRecord:
    work_order_id: WorkOrderId
    external_work_order_number: str | None
    raw_title: str | None
    raw_content: str
    raw_fields: tuple[tuple[str, str | int | float | bool | None], ...]


@dataclass(frozen=True, slots=True)
class EventInstanceRecord:
    event_id: EventInstanceId
    work_order_id: WorkOrderId
    ordinal: int
    event_type: str | None
    normalized_summary: str


@dataclass(frozen=True, slots=True)
class EventForMatching:
    event_id: EventInstanceId
    work_order_id: WorkOrderId
    event_type: str | None
    behavior: str | None
    normalized_summary: str
    entity_ids: tuple[EntityId, ...]
    location_signals: tuple[str, ...]
    time_signals: tuple[str, ...]
    evidence: tuple[dict[str, object], ...]
    raw_title: str | None
    raw_content: str


@dataclass(frozen=True, slots=True)
class EventClusterRecord:
    cluster_id: EventClusterId
    name: str
    member_ids: tuple[EventInstanceId, ...]


@dataclass(frozen=True, slots=True)
class GazetteerHealth:
    available: bool
    version: str | None = None


@dataclass(frozen=True, slots=True)
class GazetteerSnapshot:
    snapshot_hash: str
    version: str
    built_at: datetime
    entities: tuple["CanonicalEntity", ...]


@dataclass(frozen=True, slots=True)
class CanonicalEntity:
    entity_id: EntityId
    standard_name: str
    entity_type: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    entity: CanonicalEntity
    confidence: float
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EntityCandidateSet:
    mention: str
    state: ResolutionState
    candidates: tuple[EntityCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class LLMRequest:
    request_id: str
    prompt: str
    output_schema: dict[str, object]
    schema_version: str = "understanding.v1"
    pipeline_version: str = "understanding.v1"
    route: ProviderRoute = ProviderRoute.AUTO


@dataclass(frozen=True, slots=True)
class LLMResult:
    request_id: str
    structured_output: dict[str, object]
    trace: VersionTrace


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    item_id: str
    text: str
    schema_version: str = "understanding.v1"
    pipeline_version: str = "understanding.v1"
    route: ProviderRoute = ProviderRoute.AUTO


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    item_id: str
    vector: tuple[float, ...]
    model_id: str
    trace: VersionTrace | None = None


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    event_id: EventInstanceId
    entity_ids: tuple[EntityId, ...]
    location_signals: tuple[str, ...]
    event_type: str | None
    text: str
    limit: int


@dataclass(frozen=True, slots=True)
class EventCandidate:
    event_id: EventInstanceId
    score: float
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RerankRequest:
    query: RetrievalQuery
    candidates: tuple[EventCandidate, ...]


@dataclass(frozen=True, slots=True)
class SameEventEvidence:
    same_entity: bool | None
    same_location: bool | None
    same_issue: bool | None
    time_compatible: bool | None
    contradictions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SameEventDecision:
    same_event: bool
    confidence: float
    evidence: SameEventEvidence
    trace: VersionTrace


@dataclass(frozen=True, slots=True)
class EventMatchEdgeRecord:
    left_event_id: EventInstanceId
    right_event_id: EventInstanceId
    same_event: bool
    confidence: float
    evidence: SameEventEvidence
    trace: VersionTrace


@dataclass(frozen=True, slots=True)
class EventClusterMemberRecord:
    event_instance_id: EventInstanceId
    membership_confidence: float


@dataclass(frozen=True, slots=True)
class ClusterProposal:
    members: tuple[EventInstanceId, ...]
    rejected_edges: tuple[tuple[EventInstanceId, EventInstanceId], ...] = ()
    confidence: float = 0.0
    evidence: dict[str, object] = field(default_factory=_empty_object_dict)


def _empty_filters() -> dict[str, str]:
    return {}


@dataclass(frozen=True, slots=True)
class ExportRequest:
    format: str
    event_cluster_ids: tuple[EventClusterId, ...] = ()
    filters: dict[str, str] = field(default_factory=_empty_filters)


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    filename: str
    media_type: str
    content: bytes
