"""add wp2 domain data fields, event instance v3, and analysis scopes

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-16 12:00:00

WP2:
- WorkOrder: reported_at, reported_at_source,
  reported_at_parser_version, imported_at, source_tags,
  raw_payload_hash
- EventInstance V3: classification fields, evidence spans,
  focal/responsible/location mentions, occurrence interval,
  unknown fields
- AnalysisScope: frozen scope per analysis job
  (batch, work order IDs, target count, pipeline/taxonomy
  /provider snapshots)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # WorkOrder new columns
    op.add_column(
        "work_orders",
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "work_orders",
        sa.Column("reported_at_source", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "work_orders",
        sa.Column("reported_at_parser_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "work_orders",
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "work_orders",
        sa.Column(
            "source_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "work_orders",
        sa.Column("raw_payload_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_work_orders_reported_at"),
        "work_orders",
        ["reported_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_work_orders_raw_payload_hash"),
        "work_orders",
        ["raw_payload_hash"],
        unique=False,
    )

    # EventInstance V3 columns
    op.add_column(
        "event_instances",
        sa.Column("classification_node_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "event_instances",
        sa.Column("classification_source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "event_instances",
        sa.Column("classification_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "event_instances",
        sa.Column("classification_ambiguity", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "event_instances",
        sa.Column("current_problem", sa.Text(), nullable=True),
    )
    op.add_column(
        "event_instances",
        sa.Column("current_request", sa.Text(), nullable=True),
    )
    op.add_column(
        "event_instances",
        sa.Column("history_context", sa.Text(), nullable=True),
    )
    op.add_column(
        "event_instances",
        sa.Column(
            "previous_work_order_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "event_instances",
        sa.Column(
            "focal_object_mentions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "event_instances",
        sa.Column(
            "responsible_party_mentions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "event_instances",
        sa.Column(
            "location_mentions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "event_instances",
        sa.Column("occurrence_interval_start", sa.Date(), nullable=True),
    )
    op.add_column(
        "event_instances",
        sa.Column("occurrence_interval_end", sa.Date(), nullable=True),
    )
    op.add_column(
        "event_instances",
        sa.Column(
            "evidence_spans",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "event_instances",
        sa.Column(
            "unknown_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_index(
        op.f("ix_event_instances_classification_node_id"),
        "event_instances",
        ["classification_node_id"],
        unique=False,
    )

    # AnalysisScope table
    op.create_table(
        "analysis_scopes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_job_id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("target_work_order_count", sa.Integer(), nullable=False),
        sa.Column(
            "work_order_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("work_order_id_hash", sa.String(length=64), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("taxonomy_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "provider_profile_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "execution_policy_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
        sa.ForeignKeyConstraint(
            ["analysis_job_id"],
            ["analysis_jobs.id"],
            name=op.f("fk_analysis_scopes_analysis_job_id_analysis_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batches.id"],
            name=op.f("fk_analysis_scopes_import_batch_id_import_batches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["taxonomy_version_id"],
            ["taxonomy_versions.id"],
            name=op.f("fk_analysis_scopes_taxonomy_version_id_taxonomy_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_scopes")),
        sa.UniqueConstraint("analysis_job_id", name=op.f("uq_analysis_scopes_analysis_job_id")),
    )
    op.create_index(
        op.f("ix_analysis_scopes_analysis_job_id"),
        "analysis_scopes",
        ["analysis_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_scopes_import_batch_id"),
        "analysis_scopes",
        ["import_batch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_analysis_scopes_import_batch_id"), table_name="analysis_scopes")
    op.drop_index(op.f("ix_analysis_scopes_analysis_job_id"), table_name="analysis_scopes")
    op.drop_table("analysis_scopes")

    op.drop_index(op.f("ix_event_instances_classification_node_id"), table_name="event_instances")
    op.drop_column("event_instances", "unknown_fields")
    op.drop_column("event_instances", "evidence_spans")
    op.drop_column("event_instances", "occurrence_interval_end")
    op.drop_column("event_instances", "occurrence_interval_start")
    op.drop_column("event_instances", "location_mentions")
    op.drop_column("event_instances", "responsible_party_mentions")
    op.drop_column("event_instances", "focal_object_mentions")
    op.drop_column("event_instances", "previous_work_order_references")
    op.drop_column("event_instances", "history_context")
    op.drop_column("event_instances", "current_request")
    op.drop_column("event_instances", "current_problem")
    op.drop_column("event_instances", "classification_ambiguity")
    op.drop_column("event_instances", "classification_confidence")
    op.drop_column("event_instances", "classification_source")
    op.drop_column("event_instances", "classification_node_id")

    op.drop_index(op.f("ix_work_orders_raw_payload_hash"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_reported_at"), table_name="work_orders")
    op.drop_column("work_orders", "raw_payload_hash")
    op.drop_column("work_orders", "source_tags")
    op.drop_column("work_orders", "imported_at")
    op.drop_column("work_orders", "reported_at_parser_version")
    op.drop_column("work_orders", "reported_at_source")
    op.drop_column("work_orders", "reported_at")
