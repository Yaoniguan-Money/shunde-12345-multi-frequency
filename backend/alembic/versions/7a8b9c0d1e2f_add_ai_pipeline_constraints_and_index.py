"""add AI pipeline idempotency constraints and pgvector index

Revision ID: 7a8b9c0d1e2f
Revises: 6b7c8d9e0f10
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "7a8b9c0d1e2f"
down_revision: str | None = "6b7c8d9e0f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_analysis_runs_job_run_number", "analysis_runs", ["analysis_job_id", "run_number"]
    )
    op.create_unique_constraint(
        "uq_complaint_segments_work_order_ordinal",
        "complaint_segments",
        ["work_order_id", "ordinal"],
    )
    op.create_unique_constraint(
        "uq_event_instances_work_order_ordinal_pipeline",
        "event_instances",
        ["work_order_id", "ordinal", "pipeline_version"],
    )
    op.create_unique_constraint(
        "uq_entity_mentions_work_order_ordinal_pipeline",
        "entity_mentions",
        ["work_order_id", "ordinal", "pipeline_version"],
    )
    op.execute(
        """
        CREATE INDEX ix_work_order_embeddings_embedding_cosine_hnsw
        ON work_order_embeddings
        USING hnsw ((embedding::vector(768)) vector_cosine_ops)
        WHERE dimensions = 768
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_work_order_embeddings_embedding_cosine_hnsw")
    op.drop_constraint(
        "uq_entity_mentions_work_order_ordinal_pipeline", "entity_mentions", type_="unique"
    )
    op.drop_constraint(
        "uq_event_instances_work_order_ordinal_pipeline", "event_instances", type_="unique"
    )
    op.drop_constraint(
        "uq_complaint_segments_work_order_ordinal", "complaint_segments", type_="unique"
    )
    op.drop_constraint("uq_analysis_runs_job_run_number", "analysis_runs", type_="unique")
