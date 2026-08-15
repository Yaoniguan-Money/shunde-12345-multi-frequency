"""add taxonomy tables

Revision ID: b1c2d3e4f5a6
Revises: ad1e2f3a4b5c
Create Date: 2026-08-16 03:00:00

WP1: DB44/T 2479—2024 附录 A 版本化主数据。
- taxonomy_versions: 版本元信息 + 完整性统计
- taxonomy_nodes: 14 一级 + 99 二级 + 515 三级节点，保留 090499 两条和 13 条空三级名称
- partial unique index 保证同一时刻只有一个 active version
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "ad1e2f3a4b5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("standard_name", sa.String(length=255), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("extracted_resource_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("level_1_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_2_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_3_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("distinct_level_3_code_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("empty_level_3_name_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "duplicate_printed_codes",
            postgresql.ARRAY(sa.String(length=16)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_taxonomy_versions")),
        sa.UniqueConstraint(
            "standard_name",
            "source_sha256",
            "extracted_resource_sha256",
            name=op.f("uq_taxonomy_versions_standard_name_source_sha256_extracted_resource_sha256"),
        ),
    )
    op.create_index(
        op.f("ix_taxonomy_versions_status"), "taxonomy_versions", ["status"], unique=False
    )
    # Partial unique index: 同一时刻只有一个 active version
    op.create_index(
        "uq_taxonomy_versions_active_single",
        "taxonomy_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "taxonomy_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("taxonomy_version_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.String(length=128), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("printed_code", sa.String(length=16), nullable=False),
        sa.Column("printed_name", sa.String(length=255), nullable=True),
        sa.Column("parent_node_db_id", sa.Uuid(), nullable=True),
        sa.Column(
            "full_path",
            postgresql.ARRAY(sa.String(length=16)),
            nullable=False,
        ),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_anomaly", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("display_name_source", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["taxonomy_version_id"],
            ["taxonomy_versions.id"],
            name=op.f("fk_taxonomy_nodes_taxonomy_version_id_taxonomy_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_node_db_id"],
            ["taxonomy_nodes.id"],
            name=op.f("fk_taxonomy_nodes_parent_node_db_id_taxonomy_nodes"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_taxonomy_nodes")),
        sa.UniqueConstraint(
            "taxonomy_version_id",
            "node_id",
            name=op.f("uq_taxonomy_nodes_taxonomy_version_id_node_id"),
        ),
    )
    op.create_index(
        op.f("ix_taxonomy_nodes_taxonomy_version_id"),
        "taxonomy_nodes",
        ["taxonomy_version_id"],
        unique=False,
    )
    op.create_index(op.f("ix_taxonomy_nodes_node_id"), "taxonomy_nodes", ["node_id"], unique=False)
    op.create_index(op.f("ix_taxonomy_nodes_level"), "taxonomy_nodes", ["level"], unique=False)
    op.create_index(
        op.f("ix_taxonomy_nodes_printed_code"),
        "taxonomy_nodes",
        ["printed_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_taxonomy_nodes_full_path"),
        "taxonomy_nodes",
        ["full_path"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_taxonomy_nodes_source_anomaly"),
        "taxonomy_nodes",
        ["source_anomaly"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_taxonomy_nodes_source_anomaly"), table_name="taxonomy_nodes")
    op.drop_index(op.f("ix_taxonomy_nodes_full_path"), table_name="taxonomy_nodes")
    op.drop_index(op.f("ix_taxonomy_nodes_printed_code"), table_name="taxonomy_nodes")
    op.drop_index(op.f("ix_taxonomy_nodes_level"), table_name="taxonomy_nodes")
    op.drop_index(op.f("ix_taxonomy_nodes_node_id"), table_name="taxonomy_nodes")
    op.drop_index(op.f("ix_taxonomy_nodes_taxonomy_version_id"), table_name="taxonomy_nodes")
    op.drop_table("taxonomy_nodes")
    op.drop_index("uq_taxonomy_versions_active_single", table_name="taxonomy_versions")
    op.drop_index(op.f("ix_taxonomy_versions_status"), table_name="taxonomy_versions")
    op.drop_table("taxonomy_versions")
