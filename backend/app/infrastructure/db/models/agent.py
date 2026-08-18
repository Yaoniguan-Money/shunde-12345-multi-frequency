"""Persistent, auditable records owned by the natural-language Agent module."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "worksets"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_query: Mapped[str] = mapped_column(Text, nullable=False)
    query_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class WorksetWorkOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workset_work_orders"
    __table_args__ = (UniqueConstraint("workset_id", "work_order_id"),)

    workset_id: Mapped[UUID] = mapped_column(
        ForeignKey("worksets.id", ondelete="CASCADE"), index=True
    )
    work_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )


class WorksetCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workset_clusters"
    __table_args__ = (UniqueConstraint("workset_id", "cluster_id"),)

    workset_id: Mapped[UUID] = mapped_column(
        ForeignKey("worksets.id", ondelete="CASCADE"), index=True
    )
    cluster_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE"), index=True
    )


class WorkOrderHandlingRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "work_order_handling_records"

    work_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    previous_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)


class AgentActionPreview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_action_previews"

    workset_id: Mapped[UUID] = mapped_column(
        ForeignKey("worksets.id", ondelete="CASCADE"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    preview_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
