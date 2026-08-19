"""Historical compatibility marker for an already-deployed database revision.

Revision ID: d3e4f5a6b7c8
Revises: ad1e2f3a4b5c
Create Date: 2026-08-19

The original revision was absent from the handed-off repository while deployed
databases already recorded it.  This marker restores a traversable Alembic
history without replaying potentially destructive historical DDL.
"""

revision = "d3e4f5a6b7c8"
down_revision = "ad1e2f3a4b5c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
