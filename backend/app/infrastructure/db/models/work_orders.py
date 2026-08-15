from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_batches"

    source_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    source_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    field_mapping: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checkpoint_row: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class WorkOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "work_orders"
    __table_args__ = (UniqueConstraint("import_batch_id", "source_row_number"),)

    import_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), index=True
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    external_work_order_number: Mapped[str | None] = mapped_column(String(255), index=True)
    raw_title: Mapped[str | None] = mapped_column(Text)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    raw_fields: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    reported_at_source: Mapped[str | None] = mapped_column(String(64))
    reported_at_parser_version: Mapped[str | None] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64), index=True)


class ComplaintSegment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "complaint_segments"
    __table_args__ = (UniqueConstraint("work_order_id", "ordinal"),)

    work_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    segment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)


class ImportRowError(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_row_errors"
    __table_args__ = (UniqueConstraint("import_batch_id", "source_row_number", "error_code"),)

    import_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), index=True
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
