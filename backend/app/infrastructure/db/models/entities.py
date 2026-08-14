from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.models.base import (
    AITraceMixin,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class KnowledgeSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_snapshots"

    version: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    source_version: Mapped[str | None] = mapped_column(String(128))
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class CanonicalEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "canonical_entities"
    __table_args__ = (UniqueConstraint("source_namespace", "source_entity_key"),)

    source_namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    source_entity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    standard_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    administrative_code: Mapped[str | None] = mapped_column(String(32), index=True)
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class EntityAliasRuntime(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entity_aliases_runtime"
    __table_args__ = (UniqueConstraint("knowledge_snapshot_id", "alias", "canonical_entity_id"),)

    knowledge_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_snapshots.id", ondelete="CASCADE"), index=True
    )
    canonical_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("canonical_entities.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    alias_type: Mapped[str] = mapped_column(String(64), nullable=False)


class EntityMention(UUIDPrimaryKeyMixin, AITraceMixin, TimestampMixin, Base):
    __tablename__ = "entity_mentions"
    __table_args__ = (UniqueConstraint("work_order_id", "ordinal", "pipeline_version"),)

    work_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    complaint_segment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("complaint_segments.id", ondelete="CASCADE"), index=True
    )
    mention_text: Mapped[str] = mapped_column(Text, nullable=False)
    mention_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    canonical_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("canonical_entities.id", ondelete="SET NULL"), index=True
    )
    resolution_state: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
