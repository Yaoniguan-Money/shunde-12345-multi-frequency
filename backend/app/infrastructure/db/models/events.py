from datetime import date
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.models.base import (
    AITraceMixin,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class EventInstance(UUIDPrimaryKeyMixin, AITraceMixin, TimestampMixin, Base):
    __tablename__ = "event_instances"
    __table_args__ = (UniqueConstraint("work_order_id", "ordinal", "pipeline_version"),)

    work_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(128), index=True)
    behavior: Mapped[str | None] = mapped_column(Text)
    normalized_summary: Mapped[str] = mapped_column(Text, nullable=False)
    entity_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    location_signals: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    time_signals: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    occurrence_date: Mapped[date | None] = mapped_column(Date, index=True)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    # V3 fields (understanding.v3)
    classification_node_id: Mapped[str | None] = mapped_column(String(128), index=True)
    classification_source: Mapped[str | None] = mapped_column(String(32))
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    classification_ambiguity: Mapped[str | None] = mapped_column(String(32))
    current_problem: Mapped[str | None] = mapped_column(Text)
    current_request: Mapped[str | None] = mapped_column(Text)
    history_context: Mapped[str | None] = mapped_column(Text)
    previous_work_order_references: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    focal_object_mentions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    responsible_party_mentions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    location_mentions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    occurrence_interval_start: Mapped[date | None] = mapped_column(Date)
    occurrence_interval_end: Mapped[date | None] = mapped_column(Date)
    evidence_spans: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    unknown_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class WorkOrderEmbedding(UUIDPrimaryKeyMixin, AITraceMixin, TimestampMixin, Base):
    __tablename__ = "work_order_embeddings"
    __table_args__ = (UniqueConstraint("work_order_id", "content_hash", "model_id"),)

    work_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    event_instance_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("event_instances.id", ondelete="CASCADE"), index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)


class EventCandidate(UUIDPrimaryKeyMixin, AITraceMixin, TimestampMixin, Base):
    __tablename__ = "event_candidates"
    __table_args__ = (UniqueConstraint("query_event_id", "candidate_event_id", "analysis_run_id"),)

    query_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_instances.id", ondelete="CASCADE"), index=True
    )
    candidate_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_instances.id", ondelete="CASCADE"), index=True
    )
    analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    retrieval_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_score: Mapped[float] = mapped_column(Float, nullable=False)
    rerank_score: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class EventMatchEdge(UUIDPrimaryKeyMixin, AITraceMixin, TimestampMixin, Base):
    __tablename__ = "event_match_edges"
    __table_args__ = (UniqueConstraint("left_event_id", "right_event_id", "analysis_run_id"),)

    left_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_instances.id", ondelete="CASCADE"), index=True
    )
    right_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_instances.id", ondelete="CASCADE"), index=True
    )
    analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    same_event: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class EventCluster(UUIDPrimaryKeyMixin, AITraceMixin, TimestampMixin, Base):
    __tablename__ = "event_clusters"

    name: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    handling_status: Mapped[str] = mapped_column(String(32), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_review")
    member_signature: Mapped[str | None] = mapped_column(String(64), unique=True)


class EventClusterMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_cluster_members"
    __table_args__ = (UniqueConstraint("event_cluster_id", "event_instance_id"),)

    event_cluster_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE"), index=True
    )
    event_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_instances.id", ondelete="CASCADE"), index=True
    )
    analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    membership_confidence: Mapped[float] = mapped_column(Float, nullable=False)
