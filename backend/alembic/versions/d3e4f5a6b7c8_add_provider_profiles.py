"""add durable provider profile registry

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_profiles",
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("deployment_kind", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("configured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_display_name", sa.String(length=255), nullable=True),
        sa.Column("service_description", sa.String(length=1000), nullable=False),
        sa.Column("configuration_version", sa.String(length=255), nullable=False),
        sa.Column(
            "adapter_config",
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
        sa.PrimaryKeyConstraint("profile_id", name=op.f("pk_provider_profiles")),
    )


def downgrade() -> None:
    op.drop_table("provider_profiles")
