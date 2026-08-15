"""add the selected Qwen remote embedding HNSW index

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9c0d1e2f3a4b"
down_revision: str | None = "8b9c0d1e2f3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Dimensions were measured from a real qwen3.7-text-embedding response.
    op.execute(
        """
        CREATE INDEX ix_work_order_embeddings_qwen37_text_embedding_hnsw
        ON work_order_embeddings
        USING hnsw ((embedding::vector(1024)) vector_cosine_ops)
        WHERE dimensions = 1024 AND model_id = 'qwen3.7-text-embedding'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_work_order_embeddings_qwen37_text_embedding_hnsw")
