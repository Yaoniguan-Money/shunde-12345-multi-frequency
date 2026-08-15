"""add product semantics contracts

Revision ID: ad1e2f3a4b5c
Revises: 9c0d1e2f3a4b
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad1e2f3a4b5c"
down_revision: str | None = "9c0d1e2f3a4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("event_instances", sa.Column("occurrence_date", sa.Date(), nullable=True))
    op.create_index("ix_event_instances_occurrence_date", "event_instances", ["occurrence_date"])
    op.add_column(
        "event_clusters",
        sa.Column(
            "review_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending_review",
        ),
    )
    op.add_column(
        "event_clusters", sa.Column("member_signature", sa.String(length=64), nullable=True)
    )
    op.create_unique_constraint(
        "uq_event_clusters_member_signature", "event_clusters", ["member_signature"]
    )
    op.create_table(
        "work_order_analysis_results",
        sa.Column("work_order_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "work_order_id",
            "analysis_run_id",
            "pipeline_version",
            name="uq_work_order_analysis_result_run",
        ),
    )
    for column in ("work_order_id", "analysis_run_id", "pipeline_version", "status"):
        op.create_index(
            f"ix_work_order_analysis_results_{column}",
            "work_order_analysis_results",
            [column],
        )
    op.execute(
        """
        UPDATE event_instances AS event
        SET entity_ids = COALESCE(
          (
            SELECT jsonb_agg(ref.entity_id)
            FROM jsonb_array_elements_text(event.entity_ids) AS ref(entity_id)
            JOIN canonical_entities AS entity ON entity.id::text = ref.entity_id
          ),
          '[]'::jsonb
        )
        WHERE EXISTS (
          SELECT 1
          FROM jsonb_array_elements_text(event.entity_ids) AS ref(entity_id)
          LEFT JOIN canonical_entities AS entity ON entity.id::text = ref.entity_id
          WHERE entity.id IS NULL
        )
        """
    )


def downgrade() -> None:
    for column in ("status", "pipeline_version", "analysis_run_id", "work_order_id"):
        op.drop_index(f"ix_work_order_analysis_results_{column}")
    op.drop_table("work_order_analysis_results")
    op.drop_constraint("uq_event_clusters_member_signature", "event_clusters", type_="unique")
    op.drop_column("event_clusters", "member_signature")
    op.drop_column("event_clusters", "review_status")
    op.drop_index("ix_event_instances_occurrence_date", table_name="event_instances")
    op.drop_column("event_instances", "occurrence_date")
