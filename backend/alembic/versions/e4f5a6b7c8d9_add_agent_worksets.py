"""add Agent worksets, work-order handling history and action previews

Revision ID: e4f5a6b7c8d9
Revises: ad1e2f3a4b5c
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "ad1e2f3a4b5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worksets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("original_query", sa.Text(), nullable=False),
        sa.Column("query_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "workset_work_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workset_id", sa.Uuid(), nullable=False),
        sa.Column("work_order_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["workset_id"], ["worksets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workset_id", "work_order_id"),
    )
    op.create_index("ix_workset_work_orders_workset_id", "workset_work_orders", ["workset_id"])
    op.create_index(
        "ix_workset_work_orders_work_order_id", "workset_work_orders", ["work_order_id"]
    )
    op.create_table(
        "workset_clusters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workset_id", sa.Uuid(), nullable=False),
        sa.Column("cluster_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["workset_id"], ["worksets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cluster_id"], ["event_clusters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workset_id", "cluster_id"),
    )
    op.create_index("ix_workset_clusters_workset_id", "workset_clusters", ["workset_id"])
    op.create_index("ix_workset_clusters_cluster_id", "workset_clusters", ["cluster_id"])
    op.create_table(
        "work_order_handling_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_order_id", sa.Uuid(), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_work_order_handling_records_work_order_id",
        "work_order_handling_records",
        ["work_order_id"],
    )
    op.create_table(
        "agent_action_previews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workset_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preview_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["workset_id"], ["worksets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_action_previews_workset_id", "agent_action_previews", ["workset_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_action_previews_workset_id", table_name="agent_action_previews")
    op.drop_table("agent_action_previews")
    op.drop_index(
        "ix_work_order_handling_records_work_order_id", table_name="work_order_handling_records"
    )
    op.drop_table("work_order_handling_records")
    op.drop_index("ix_workset_clusters_cluster_id", table_name="workset_clusters")
    op.drop_index("ix_workset_clusters_workset_id", table_name="workset_clusters")
    op.drop_table("workset_clusters")
    op.drop_index("ix_workset_work_orders_work_order_id", table_name="workset_work_orders")
    op.drop_index("ix_workset_work_orders_workset_id", table_name="workset_work_orders")
    op.drop_table("workset_work_orders")
    op.drop_table("worksets")
