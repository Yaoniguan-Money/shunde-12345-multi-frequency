from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.domain.imports import (
    ImportBatchSpec,
    ImportBatchState,
    ImportRow,
    ImportRowFailure,
)
from backend.app.domain.ports.imports import ImportBatchRepository
from backend.app.domain.work_orders import canonical_root_work_order_number
from backend.app.infrastructure.db.models import ImportBatch, ImportRowError, WorkOrder


class SQLAlchemyImportRepository(ImportBatchRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def start_or_resume(self, spec: ImportBatchSpec) -> ImportBatchState:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    batch = await session.scalar(
                        select(ImportBatch).where(ImportBatch.source_sha256 == spec.source_sha256)
                    )
                    if batch is None:
                        batch = ImportBatch(
                            source_filename=spec.filename,
                            source_sha256=spec.source_sha256,
                            source_size_bytes=spec.source_size_bytes,
                            sheet_name=spec.sheet_name,
                            field_mapping=spec.mapping.as_dict(),
                            total_rows=spec.total_rows,
                            status="running",
                        )
                        session.add(batch)
                        await session.flush()
                        return self._state(batch, idempotent=False)
                    return self._resume_existing(batch, spec.total_rows)
        except IntegrityError:
            # Another worker may have inserted the same content hash between the
            # initial read and flush. Re-read after rollback and follow the same
            # idempotency/resume rules instead of creating a second batch.
            async with self._session_factory() as session:
                batch = await session.scalar(
                    select(ImportBatch).where(ImportBatch.source_sha256 == spec.source_sha256)
                )
                if batch is None:
                    raise
                return self._state(batch, idempotent=batch.status in {"completed", "partial"})

    async def persist_chunk(
        self,
        batch_id: UUID,
        rows: tuple[ImportRow, ...],
        failures: tuple[ImportRowFailure, ...],
        checkpoint_row: int,
    ) -> ImportBatchState:
        async with self._session_factory() as session:
            async with session.begin():
                batch = await self._locked_batch(session, batch_id)
                inserted = 0
                for row in rows:
                    result = cast(
                        CursorResult[Any],
                        await session.execute(
                            pg_insert(WorkOrder)
                            .values(
                                import_batch_id=batch_id,
                                source_row_number=row.source_row_number,
                                external_work_order_number=row.external_work_order_number,
                                root_work_order_number=canonical_root_work_order_number(
                                    row.external_work_order_number
                                ),
                                reported_at=row.reported_at,
                                raw_title=row.title,
                                raw_content=row.content,
                                raw_fields=row.raw_fields,
                                raw_sha256=row.raw_sha256,
                            )
                            .on_conflict_do_nothing(
                                index_elements=[
                                    WorkOrder.import_batch_id,
                                    WorkOrder.source_row_number,
                                ]
                            )
                        ),
                    )
                    if result.rowcount == 1:
                        inserted += 1
                batch.duplicate_rows += len(rows) - inserted
                failed = 0
                for failure in failures:
                    result = cast(
                        CursorResult[Any],
                        await session.execute(
                            pg_insert(ImportRowError)
                            .values(
                                import_batch_id=batch_id,
                                source_row_number=failure.source_row_number,
                                error_code=failure.error_code,
                                message=failure.message,
                            )
                            .on_conflict_do_nothing(
                                index_elements=[
                                    ImportRowError.import_batch_id,
                                    ImportRowError.source_row_number,
                                    ImportRowError.error_code,
                                ]
                            )
                        ),
                    )
                    if result.rowcount == 1:
                        failed += 1
                batch.successful_rows += inserted
                batch.failed_rows += failed
                batch.checkpoint_row = max(batch.checkpoint_row, checkpoint_row)
                return self._state(batch, idempotent=False)

    async def finish(self, batch_id: UUID) -> ImportBatchState:
        async with self._session_factory() as session:
            async with session.begin():
                batch = await self._locked_batch(session, batch_id)
                batch.status = "partial" if batch.failed_rows else "completed"
                return self._state(batch, idempotent=False)

    async def fail(self, batch_id: UUID, error_code: str, message: str) -> ImportBatchState:
        async with self._session_factory() as session:
            async with session.begin():
                batch = await self._locked_batch(session, batch_id)
                batch.status = "failed"
                batch.last_error_code = error_code
                return self._state(batch, idempotent=False)

    async def _locked_batch(self, session: AsyncSession, batch_id: UUID) -> ImportBatch:
        batch = await session.scalar(
            select(ImportBatch).where(ImportBatch.id == batch_id).with_for_update()
        )
        if batch is None:
            raise LookupError(f"import batch not found: {batch_id}")
        return batch

    @staticmethod
    def _state(batch: ImportBatch, *, idempotent: bool) -> ImportBatchState:
        return ImportBatchState(
            batch_id=batch.id,
            status=batch.status,
            checkpoint_row=batch.checkpoint_row,
            total_rows=batch.total_rows,
            successful_rows=batch.successful_rows,
            failed_rows=batch.failed_rows,
            duplicate_rows=batch.duplicate_rows,
            idempotent=idempotent,
        )

    @staticmethod
    def _resume_existing(batch: ImportBatch, total_rows: int) -> ImportBatchState:
        if batch.status in {"completed", "partial"}:
            return SQLAlchemyImportRepository._state(batch, idempotent=True)
        batch.status = "running"
        batch.last_error_code = None
        batch.total_rows = total_rows
        return SQLAlchemyImportRepository._state(batch, idempotent=False)
