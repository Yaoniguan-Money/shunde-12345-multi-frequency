"""Add source-reported timestamps and derived root work-order identities.

Revision ID: b2c3d4e5f6a7
Revises: d3e4f5a6b7c8
Create Date: 2026-08-19
"""

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS root_work_order_number VARCHAR(255)"
    )
    op.execute("ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS reported_at TIMESTAMPTZ")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_work_orders_root_work_order_number "
        "ON work_orders (root_work_order_number)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_work_orders_reported_at ON work_orders (reported_at)")
    op.execute(
        """
        UPDATE work_orders
        SET root_work_order_number = regexp_replace(external_work_order_number, '-[0-9]{2}$', '')
        WHERE external_work_order_number ~ '-[0-9]{2}$'
        """
    )
    op.execute(
        """
        UPDATE work_orders
        SET root_work_order_number = external_work_order_number
        WHERE root_work_order_number IS NULL AND external_work_order_number IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_work_orders_root_work_order_number", table_name="work_orders")
    op.drop_column("work_orders", "root_work_order_number")
