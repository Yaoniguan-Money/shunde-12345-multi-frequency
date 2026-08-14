from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import get_settings
from backend.app.infrastructure.db.session import create_engine


async def test_raw_work_order_fields_are_database_immutable() -> None:
    engine = create_engine(get_settings())
    batch_id = uuid4()
    work_order_id = uuid4()
    source_hash = uuid4().hex + uuid4().hex
    try:
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        INSERT INTO import_batches
                          (id, source_filename, source_sha256, source_size_bytes, field_mapping,
                           total_rows, successful_rows, failed_rows, duplicate_rows,
                           checkpoint_row, status)
                        VALUES (:batch_id, 'immutability-test.xlsx', :source_hash, 1, '{}'::jsonb,
                                1, 0, 0, 0, 0, 'running')
                        """
                    ),
                    {"batch_id": batch_id, "source_hash": source_hash},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO work_orders
                          (id, import_batch_id, source_row_number, raw_content, raw_fields,
                           raw_sha256)
                        VALUES (:work_order_id, :batch_id, 1, 'immutable', '{}'::jsonb, :raw_hash)
                        """
                    ),
                    {
                        "work_order_id": work_order_id,
                        "batch_id": batch_id,
                        "raw_hash": "a" * 64,
                    },
                )
        except (OSError, SQLAlchemyError) as error:
            pytest.skip(f"PostgreSQL not available; runtime immutability check deferred: {error}")

        with pytest.raises(SQLAlchemyError, match="raw work order fields are immutable"):
            async with engine.begin() as connection:
                await connection.execute(
                    text("UPDATE work_orders SET raw_content = 'changed' WHERE id = :id"),
                    {"id": work_order_id},
                )
    finally:
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("DELETE FROM import_batches WHERE id = :id"), {"id": batch_id}
                )
        except (OSError, SQLAlchemyError):
            pass
        await engine.dispose()
