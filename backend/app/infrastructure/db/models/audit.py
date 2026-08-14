from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class HumanCorrection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "human_corrections"

    correction_type: Mapped[str] = mapped_column(String(64), nullable=False)
    work_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("work_orders.id", ondelete="SET NULL"), index=True
    )
    event_cluster_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="SET NULL"), index=True
    )
    supersedes_correction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("human_corrections.id", ondelete="SET NULL")
    )
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class EventHandlingRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_handling_records"

    event_cluster_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE"), index=True
    )
    previous_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)
    attachment_references: Mapped[list[str]] = mapped_column(JSONB, nullable=False)


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    before_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    after_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
