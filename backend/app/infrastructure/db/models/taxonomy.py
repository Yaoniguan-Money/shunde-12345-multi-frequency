"""Taxonomy ORM 模型。

对应 `backend.app.domain.taxonomy` 的领域类型。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TaxonomyVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """DB44/T 2479—2024 附录 A 的版本化主数据。"""

    __tablename__ = "taxonomy_versions"
    __table_args__ = (
        # 同一时刻只有一个 active version；用 partial unique index 保证
        UniqueConstraint("standard_name", "source_sha256", "extracted_resource_sha256"),
    )

    standard_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_resource_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 完整性统计（激活时写入，便于审计）
    level_1_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level_2_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level_3_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_level_3_code_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    empty_level_3_name_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_printed_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)), nullable=False, default=list
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


class TaxonomyNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Taxonomy 节点。

    `node_id` 是稳定的逻辑标识（如 `db44t2479-2024:0904:090499`），区别于 UUID 主键。
    `printed_name` 可为 None（附录 A 有 13 条空三级名称，保真不伪造）。
    `full_path` 是从一级到本节点的完整路径数组，用于区分 `090499` 重码。
    `display_name` 和 `display_name_source` 是显示投影，不反向改写标准目录。
    """

    __tablename__ = "taxonomy_nodes"
    __table_args__ = (UniqueConstraint("taxonomy_version_id", "node_id"),)

    taxonomy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_versions.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    printed_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    printed_name: Mapped[str | None] = mapped_column(String(255))
    parent_node_db_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("taxonomy_nodes.id", ondelete="SET NULL"), index=True
    )
    full_path: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False, index=True)
    remark: Mapped[str | None] = mapped_column(Text)
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_anomaly: Mapped[str | None] = mapped_column(String(128), index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name_source: Mapped[str] = mapped_column(String(32), nullable=False)
