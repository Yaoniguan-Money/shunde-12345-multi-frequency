"""add provider provenance to AI trace records

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8b9c0d1e2f3a"
down_revision: str | None = "7a8b9c0d1e2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "analysis_runs",
    "event_instances",
    "work_order_embeddings",
    "event_candidates",
    "event_match_edges",
    "event_clusters",
    "entity_mentions",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("provider", sa.String(length=64), nullable=True))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, "provider")
