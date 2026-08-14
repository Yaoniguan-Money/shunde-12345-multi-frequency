"""add resumable import state and row errors

Revision ID: 6b7c8d9e0f10
Revises: fff93032eb16
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6b7c8d9e0f10"
down_revision: str | None = "fff93032eb16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("checkpoint_row", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("import_batches", sa.Column("last_error_code", sa.String(length=128)))
    op.create_table(
        "import_row_errors",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_batch_id", "source_row_number", "error_code"),
    )
    op.create_index(
        "ix_import_row_errors_import_batch_id", "import_row_errors", ["import_batch_id"]
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_work_order_raw_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.raw_content IS DISTINCT FROM OLD.raw_content
             OR NEW.raw_title IS DISTINCT FROM OLD.raw_title
             OR NEW.raw_fields IS DISTINCT FROM OLD.raw_fields
             OR NEW.raw_sha256 IS DISTINCT FROM OLD.raw_sha256
             OR NEW.external_work_order_number IS DISTINCT FROM OLD.external_work_order_number
             OR NEW.source_row_number IS DISTINCT FROM OLD.source_row_number
             OR NEW.import_batch_id IS DISTINCT FROM OLD.import_batch_id
          THEN
            RAISE EXCEPTION 'raw work order fields are immutable';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER work_orders_raw_immutable
        BEFORE UPDATE ON work_orders
        FOR EACH ROW EXECUTE FUNCTION prevent_work_order_raw_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS work_orders_raw_immutable ON work_orders")
    op.execute("DROP FUNCTION IF EXISTS prevent_work_order_raw_mutation()")
    op.drop_index("ix_import_row_errors_import_batch_id", table_name="import_row_errors")
    op.drop_table("import_row_errors")
    op.drop_column("import_batches", "last_error_code")
    op.drop_column("import_batches", "checkpoint_row")
